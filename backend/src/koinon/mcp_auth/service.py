# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cryptography.fernet import Fernet, InvalidToken
from pyfly.container import service
from pyfly.data import transactional
from pyfly.kernel import UnauthorizedException

from koinon.authorized_applications.service import AuthorizedApplicationService
from koinon.catalog.service import CatalogService
from koinon.mcp.settings import McpSettings
from koinon.mcp_applications.authority import McpOAuthClientAuthority
from koinon.mcp_auth.entities import McpAuthorization
from koinon.mcp_auth.repositories import McpAuthorizationRepository
from koinon.mcp_auth.settings import MCP_SCOPES, McpOAuthSettings
from koinon.tokens.service import DEPENDENCIES, PREFIX, PersonalTokenService

MCP_PREFIX = "koinon_mcp_"


class OAuthError(ValueError):
    def __init__(self, error="invalid_request", status=400):
        self.error, self.status = error, status
        super().__init__(error)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def redirect_url(uri: str, parameters: dict) -> str:
    parsed = urlsplit(uri)
    query = parse_qsl(parsed.query, keep_blank_values=True) + list(parameters.items())
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))


@service(name="mcp.oauth.service")
class McpOAuthService:
    def __init__(
        self,
        settings: McpOAuthSettings,
        mcp: McpSettings,
        repository: McpAuthorizationRepository,
        tokens: PersonalTokenService,
        catalog: CatalogService,
        applications: AuthorizedApplicationService,
        registrations: McpOAuthClientAuthority,
    ):
        self.settings, self.mcp = settings, mcp
        self.repository, self.tokens, self.catalog = repository, tokens, catalog
        self.applications = applications
        self.registrations = registrations
        if settings.enabled and not mcp.enabled:
            raise ValueError("MCP OAuth requires the MCP endpoint to be enabled")

    @property
    def origin(self):
        parsed = urlsplit(self.mcp.public_url)
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))

    @property
    def issuer(self):
        return self.origin + "/oauth2/mcp"

    @property
    def resource_metadata_url(self):
        return self.origin + "/.well-known/oauth-protected-resource/mcp"

    def require_enabled(self):
        if not self.settings.enabled or not self.mcp.enabled:
            raise OAuthError("not_found", 404)

    async def client(self, identifier: str) -> dict:
        self.require_enabled()
        try:
            return await self.registrations.resolve(identifier)
        except ValueError:
            raise OAuthError("invalid_client") from None

    async def current_client(self, identifier, tenant_id, snapshot):
        self.require_enabled()
        try:
            return await self.registrations.validate(identifier, tenant_id, snapshot)
        except ValueError:
            raise OAuthError("invalid_grant") from None

    def metadata(self):
        self.require_enabled()
        return {
            "issuer": self.issuer,
            "authorization_endpoint": self.issuer + "/authorize",
            "token_endpoint": self.issuer + "/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "authorization_response_iss_parameter_supported": True,
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
            "scopes_supported": sorted(MCP_SCOPES),
        }

    def resource_metadata(self):
        self.require_enabled()
        return {
            "resource": self.mcp.public_url,
            "authorization_servers": [self.issuer],
            "scopes_supported": self.metadata()["scopes_supported"],
            "bearer_methods_supported": ["header"],
            "resource_name": "firefly koinon",
        }

    async def validate_request(self, params: dict):
        client = await self.client(params.get("client_id", ""))
        if set(params) - {
            "client_id",
            "redirect_uri",
            "response_type",
            "resource",
            "scope",
            "state",
            "code_challenge",
            "code_challenge_method",
        }:
            raise OAuthError()
        if params.get("redirect_uri") not in client["redirect_uris"]:
            raise OAuthError()
        if params.get("resource") != self.mcp.public_url or params.get("response_type") != "code":
            raise OAuthError()
        if params.get("code_challenge_method") != "S256" or not re.fullmatch(
            r"[A-Za-z0-9_-]{43}",
            params.get("code_challenge", ""),
        ):
            raise OAuthError()
        challenge = params["code_challenge"]
        decoded = base64.urlsafe_b64decode(challenge + "=")
        if len(decoded) != 32 or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode() != challenge:
            raise OAuthError()
        scopes = set(params.get("scope", "catalog:read").split())
        for scope in tuple(scopes):
            scopes.update(DEPENDENCIES.get(scope, ()))
        if not scopes or not scopes <= MCP_SCOPES or not scopes <= set(client["scopes"]):
            raise OAuthError("invalid_scope")
        if len(params.get("state", "")) > 1024:
            raise OAuthError()
        return client, scopes

    @transactional
    async def begin(self, subject: str, params: dict):
        client, scopes = await self.validate_request(params)
        choices = []
        tenants = {member.tenant_id for member in await self.catalog.memberships(subject)}
        for tenant in sorted(tenants):
            registration = self.registrations.snapshot(client)
            if registration is not None and tenant != registration["tenant_id"]:
                continue
            organization = await self.catalog.tenant_repository.find_by_id(tenant)
            for space in await self.catalog.list(subject, tenant, kind="workspace"):
                permitted = await self.catalog.permissions(subject, tenant, space.id)
                if scopes <= permitted:
                    choices.append(
                        {
                            "tenant_id": tenant,
                            "tenant_name": organization.name if organization else tenant,
                            "workspace_id": space.id,
                            "name": space.name,
                        }
                    )
        if not choices:
            raise OAuthError("access_denied", 403)
        request_id = secrets.token_urlsafe(32)
        await self.repository.purge_expired()
        await self.repository.save(
            McpAuthorization(
                id=digest(request_id),
                subject=subject,
                client_id=client["client_id"],
                status="pending",
                request_json={**params, "scope": " ".join(sorted(scopes))},
                client_registration=self.registrations.snapshot(client),
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
        return request_id, client, sorted(scopes), choices

    @transactional
    async def consent(self, subject: str, request_id: str, decision: str, tenant_id: str, workspace_id: str):
        row = await self.repository.find_by_id(digest(request_id))
        if (
            row is None
            or row.subject != subject
            or row.status != "pending"
            or row.expires_at <= datetime.now(UTC)
        ):
            raise OAuthError()
        params = row.request_json
        snapshot = row.client_registration
        client = await self.current_client(
            row.client_id,
            snapshot["tenant_id"] if isinstance(snapshot, dict) else tenant_id,
            snapshot,
        )
        if params["redirect_uri"] not in client["redirect_uris"] or params["resource"] != self.mcp.public_url:
            raise OAuthError()
        response = {"iss": self.issuer}
        if "state" in params:
            response["state"] = params["state"]
        if decision == "deny":
            if not await self.repository.transition(row.id, subject, "pending", status="denied"):
                raise OAuthError()
            return redirect_url(params["redirect_uri"], {**response, "error": "access_denied"})
        if decision != "allow" or not tenant_id or not workspace_id:
            raise OAuthError()
        if snapshot is not None and tenant_id != snapshot["tenant_id"]:
            raise OAuthError("access_denied", 403)
        scopes = params["scope"].split()
        if not set(scopes) <= set(client["scopes"]):
            raise OAuthError("invalid_scope")
        for scope in scopes:
            await self.catalog.authorize(subject, tenant_id, scope, workspace_id)
        space = await self.catalog.get(subject, tenant_id, workspace_id)
        if space.kind != "workspace":
            raise OAuthError()
        code = secrets.token_urlsafe(32)
        if not await self.repository.transition(
            row.id,
            subject,
            "pending",
            status="code",
            code_hash=digest(code),
            grant_json={
                "tenant_id": tenant_id,
                "workspace_ids": [workspace_id],
                "name": client["name"],
                "tenant_name": (await self.catalog.tenant_repository.find_by_id(tenant_id)).name,
                "workspace_name": space.name,
            },
            expires_at=datetime.now(UTC) + timedelta(seconds=self.settings.code_ttl_seconds),
        ):
            raise OAuthError()
        return redirect_url(params["redirect_uri"], {**response, "code": code})

    @transactional
    async def exchange(self, params: dict, *, client_secret: str = ""):
        client = await self.client(params.get("client_id", ""))
        expected = client.get("client_secret_hash")
        if expected and not hmac.compare_digest(expected, digest(client_secret)):
            raise OAuthError("invalid_client", 401)
        if not expected and client_secret:
            raise OAuthError("invalid_client", 401)
        if set(params) - {"grant_type", "client_id", "code", "redirect_uri", "code_verifier", "resource"}:
            raise OAuthError()
        if params.get("grant_type") != "authorization_code":
            raise OAuthError("unsupported_grant_type")
        verifier = params.get("code_verifier", "")
        if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
            raise OAuthError("invalid_grant")
        code = params.get("code", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", code):
            raise OAuthError("invalid_grant")
        rows = await self.repository.find_all(code_hash=digest(code))
        row = rows[0] if rows else None
        if row is None or row.status != "code" or row.client_id != client["client_id"]:
            raise OAuthError("invalid_grant")
        original = row.request_json
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()
        )
        if (
            row.expires_at <= datetime.now(UTC)
            or params.get("resource") != self.mcp.public_url
            or original["resource"] != params.get("resource")
            or original["redirect_uri"] != params.get("redirect_uri")
            or params.get("redirect_uri") not in client["redirect_uris"]
            or not hmac.compare_digest(original["code_challenge"], challenge)
            or not set(original["scope"].split()) <= set(client["scopes"])
        ):
            raise OAuthError("invalid_grant")
        grant = row.grant_json
        if (
            not isinstance(grant, dict)
            or any(
                not isinstance(grant.get(key), str) or not grant[key]
                for key in ("tenant_id", "tenant_name", "workspace_name", "name")
            )
            or not isinstance(grant.get("workspace_ids"), list)
            or len(grant["workspace_ids"]) != 1
            or not isinstance(grant["workspace_ids"][0], str)
        ):
            raise OAuthError("invalid_grant")
        client = await self.current_client(
            row.client_id,
            grant["tenant_id"],
            row.client_registration,
        )
        if not await self.repository.transition(row.id, row.subject, "code", status="used"):
            raise OAuthError("invalid_grant")
        expires = datetime.now(UTC) + timedelta(seconds=self.settings.access_ttl_seconds)
        application, created = await self.applications.issue(
            row.subject,
            client_id=client["client_id"],
            name=grant["name"],
            resource=self.mcp.public_url,
            tenant_id=grant["tenant_id"],
            tenant_name=grant["tenant_name"],
            workspace_id=grant["workspace_ids"][0],
            workspace_name=grant["workspace_name"],
            scopes=original["scope"].split(),
            expires_at=expires,
            client_registration=self.registrations.snapshot(client),
        )
        payload = json.dumps(
            {
                "pat": created["token"],
                "grant_id": application.id,
                "aud": self.mcp.public_url,
                "client_id": client["client_id"],
                "exp": int(expires.timestamp()),
                "client_registration": self.registrations.snapshot(client),
            },
            separators=(",", ":"),
        ).encode()
        opaque = MCP_PREFIX + Fernet(self.settings.encryption_key.encode()).encrypt(payload).decode()
        return {
            "access_token": opaque,
            "token_type": "Bearer",
            "expires_in": self.settings.access_ttl_seconds,
            "scope": " ".join(created["scopes"]),
        }

    async def _authenticate(self, raw: str):
        if not isinstance(raw, str) or len(raw) > 8192:
            raise UnauthorizedException("Invalid MCP credential", code="INVALID_TOKEN")
        if raw.startswith(PREFIX):
            return raw, await self.tokens.authenticate(raw)
        try:
            self.require_enabled()
            if not raw.startswith(MCP_PREFIX):
                raise ValueError()
            payload = json.loads(
                Fernet(self.settings.encryption_key.encode()).decrypt(
                    raw[len(MCP_PREFIX) :].encode(),
                    ttl=self.settings.access_ttl_seconds,
                )
            )
            if (
                payload.get("aud") != self.mcp.public_url
                or payload.get("exp", 0) <= datetime.now(UTC).timestamp()
                or not isinstance(payload.get("pat"), str)
                or not payload["pat"].startswith(PREFIX)
            ):
                raise ValueError()
            client = await self.client(payload.get("client_id", ""))
            context = await self.tokens.authenticate(
                payload["pat"], purpose="application", application_id=payload.get("grant_id")
            )
            application = await self.applications.repository.find_by_id(payload.get("grant_id"))
            if (
                application is None
                or application.client_id != client["client_id"]
                or application.resource != payload["aud"]
                or application.client_registration != payload.get("client_registration")
            ):
                raise ValueError()
            client = await self.registrations.validate_application(application)
            grant = context.attributes["koinon_token"]
            if not isinstance(grant, dict) or not set(grant["scopes"]) <= set(client["scopes"]):
                raise ValueError()
            return payload["pat"], context
        except (ValueError, TypeError, KeyError, InvalidToken, UnicodeError):
            raise UnauthorizedException("Invalid or expired MCP credential", code="INVALID_TOKEN") from None

    async def canonical_bearer(self, raw: str) -> str:
        return (await self._authenticate(raw))[0]

    async def authenticate(self, raw: str):
        return (await self._authenticate(raw))[1]

    async def can_request_scopes(self, raw: str, required_scopes: tuple[str, ...]) -> bool:
        if not isinstance(raw, str) or not raw.startswith(MCP_PREFIX) or not required_scopes:
            return False
        try:
            context = await self.authenticate(raw)
            grant = context.attributes["koinon_token"]
            if not isinstance(grant, dict) or set(required_scopes) <= set(grant["scopes"]):
                return False
            payload = json.loads(
                Fernet(self.settings.encryption_key.encode()).decrypt(
                    raw[len(MCP_PREFIX) :].encode(),
                    ttl=self.settings.access_ttl_seconds,
                )
            )
            client = await self.client(payload["client_id"])
            return set(required_scopes) <= set(client["scopes"])
        except (UnauthorizedException, ValueError, TypeError, KeyError, InvalidToken, UnicodeError):
            return False
