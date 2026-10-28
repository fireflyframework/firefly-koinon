# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from pyfly.container import service
from pyfly.data import transactional
from pyfly.data.relational.sqlalchemy import LockMode
from pyfly.kernel import InvalidRequestException, UnauthorizedException
from pyfly.security.context import SecurityContext

from koinon.authorized_applications.entities import credential_matches
from koinon.authorized_applications.repositories import AuthorizedApplicationRepository
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.profiles.service import ProfileService
from koinon.tokens.entities import PersonalToken
from koinon.tokens.mappers import token_dto
from koinon.tokens.repositories import PersonalTokenRepository
from koinon.tokens.settings import TokenSettings

PREFIX = "koinon_pat_"
PERSONAL_SCOPES = {"profile:read", "profile:write"}
DEPENDENCIES = {
    "catalog:write": {"catalog:read"},
    "knowledge:search": {"catalog:read"},
    "query:execute": {"catalog:read"},
    "chat:use": {"catalog:read"},
    "ingest:write": {"catalog:read", "catalog:write"},
    "profile:write": {"profile:read"},
    "exports:read": {"catalog:read"},
    "exports:write": {"catalog:read", "exports:read"},
    "shares:read": {"catalog:read", "chat:use"},
    "shares:write": {"catalog:read", "chat:use", "shares:read"},
    "evidence:read": {"catalog:read"},
}
RESOURCE_SCOPES = {
    "catalog:read",
    "catalog:write",
    "knowledge:search",
    "query:execute",
    "chat:use",
    "ingest:write",
    "exports:read",
    "exports:write",
    "shares:read",
    "shares:write",
    "evidence:read",
}


@service(name="tokens.service")
class PersonalTokenService:
    def __init__(
        self,
        repository: PersonalTokenRepository,
        catalog: CatalogService,
        settings: TokenSettings,
        profiles: ProfileService,
        applications: AuthorizedApplicationRepository | None = None,
    ):
        self.repository, self.catalog, self.settings, self.profiles = repository, catalog, settings, profiles
        self.applications = applications

    async def list(self, subject: str) -> list[dict]:
        return [token_dto(row) for row in await self.repository.find_all(subject=subject, purpose="personal")]

    @transactional(read_only=True)
    async def page(
        self,
        subject: str,
        *,
        q="",
        status="all",
        page=1,
        page_size=25,
        sort="created_at",
        order="desc",
    ) -> dict:
        from koinon.web.pagination import sql_page

        if status not in {"all", "active", "expired", "revoked"}:
            raise InvalidRequestException("Choose a supported token status", code="INVALID_FILTER")
        predicates = [PersonalToken.subject == subject, PersonalToken.purpose == "personal"]
        now = datetime.now(UTC)
        if status in {"active", "expired"}:
            predicates.append(PersonalToken.revoked_at.is_(None))
            predicates.append(
                PersonalToken.expires_at > now if status == "active" else PersonalToken.expires_at <= now
            )
        elif status == "revoked":
            predicates.append(PersonalToken.revoked_at.is_not(None))
        result = await sql_page(
            PersonalToken,
            predicates,
            page=page,
            page_size=page_size,
            q=q,
            search=("name", "prefix"),
            sort=sort,
            order=order,
            sorts=("name", "created_at", "expires_at", "last_used_at"),
        )
        return {**result, "items": [token_dto(row) for row in result["items"]]}

    @transactional
    async def create(self, subject: str, values: dict) -> dict:
        if set(values) - {"name", "tenant_id", "scopes", "workspace_ids", "asset_ids", "expires_at"}:
            raise InvalidRequestException("Only personal token fields may be supplied", code="INVALID_TOKEN")
        return await self._issue(subject, values, purpose="personal")

    @transactional
    async def issue_application(self, subject: str, values: dict, application_id: str) -> dict:
        if self.applications is None:
            raise InvalidRequestException(
                "Application connections are unavailable", code="APPLICATION_UNAVAILABLE"
            )
        return await self._issue(subject, values, purpose="application", application_id=application_id)

    async def _issue(self, subject: str, values: dict, *, purpose: str, application_id=None) -> dict:
        tenant, scopes = values["tenant_id"], set(values["scopes"])
        workspaces, assets = values.get("workspace_ids"), values.get("asset_ids")
        if not values["name"].strip():
            raise InvalidRequestException("Enter a token name", code="INVALID_TOKEN_NAME")
        memberships = [row for row in await self.catalog.memberships(subject) if row.tenant_id == tenant]
        if not memberships:
            raise AccessDenied("Organization access is required", code="ACCESS_DENIED")
        if workspaces is None and not any(row.workspace_id is None for row in memberships):
            workspaces = list(dict.fromkeys(row.workspace_id for row in memberships))
        if workspaces is not None and not workspaces:
            raise InvalidRequestException("Choose at least one space", code="INVALID_TOKEN_SCOPE")
        available = None
        for workspace in workspaces if workspaces is not None else [None]:
            if workspace is not None:
                selected = await self.catalog.get(subject, tenant, workspace)
                if selected.kind != "workspace":
                    raise InvalidRequestException("Select a valid space", code="INVALID_TOKEN_SCOPE")
            permissions = set(await self.catalog.permissions(subject, tenant, workspace)) | PERSONAL_SCOPES
            available = permissions if available is None else available & permissions
        for scope in tuple(scopes):
            scopes.update(DEPENDENCIES.get(scope, ()))
        if not scopes or not scopes <= (available or set()):
            raise AccessDenied("A token cannot exceed your current permissions", code="TOKEN_SCOPE_DENIED")
        if (workspaces is not None or assets is not None) and not scopes <= RESOURCE_SCOPES | PERSONAL_SCOPES:
            raise InvalidRequestException(
                "Management scopes require organization scope", code="INVALID_TOKEN_SCOPE"
            )
        resources = set()
        if assets is not None:
            for asset_id in assets:
                entry = await self.catalog.get(subject, tenant, asset_id)
                if entry.kind not in {"document", "dataset", "knowledge_item"} or (
                    workspaces is not None and entry.workspace_id not in workspaces
                ):
                    raise AccessDenied("Knowledge exceeds the selected scope", code="TOKEN_SCOPE_DENIED")
                seen = set()
                while entry is not None and entry.id not in seen and len(seen) < 16:
                    seen.add(entry.id)
                    resources.add(entry.id)
                    entry = (
                        await self.catalog.get(subject, tenant, entry.parent_id) if entry.parent_id else None
                    )
        expires, now = values["expires_at"], datetime.now(UTC)
        if expires.tzinfo is None or not now + timedelta(seconds=60) <= expires <= now + timedelta(
            days=self.settings.max_lifetime_days
        ):
            raise InvalidRequestException("Choose a permitted future expiry", code="INVALID_TOKEN_EXPIRY")
        await self.profiles.lock_owner(subject)
        if purpose == "personal":
            active = [
                row
                for row in await self.repository.find_all(subject=subject, purpose="personal")
                if not row.revoked_at and row.expires_at > now
            ]
            if len(active) >= self.settings.max_active_per_user:
                raise InvalidRequestException("Revoke an existing token first", code="TOKEN_LIMIT_REACHED")
        token_id = uuid4().hex
        raw = PREFIX + token_id + "." + secrets.token_urlsafe(32)
        row = PersonalToken(
            id=token_id,
            purpose=purpose,
            authorized_application_id=application_id,
            subject=subject,
            tenant_id=tenant,
            name=values["name"].strip(),
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            prefix=PREFIX + token_id[:8],
            scopes=sorted(scopes),
            workspace_ids=workspaces,
            asset_ids=assets,
            resource_ids=sorted(resources) if assets is not None else None,
            expires_at=expires,
        )
        if purpose == "application":
            application = await self.applications.find_by_id(application_id) if self.applications else None
            if not credential_matches(application, row, now):
                raise AccessDenied(
                    "Application credentials must match their connection", code="TOKEN_SCOPE_DENIED"
                )
            if await self.repository.find_all(authorized_application_id=application_id):
                raise InvalidRequestException(
                    "This connection already has its credential", code="APPLICATION_CREDENTIAL_EXISTS"
                )
        row = await self.repository.save(row)
        await self.catalog._audit(
            subject,
            tenant,
            "token.created" if purpose == "personal" else "application.credential_issued",
            row.id,
            {"scopes": row.scopes, "expires_at": expires.isoformat()},
        )
        return {**token_dto(row), "token": raw}

    @transactional
    async def authenticate(self, token: str, *, purpose="personal", application_id=None) -> SecurityContext:
        try:
            token_id, secret = token.removeprefix(PREFIX).split(".", 1)
            if len(token_id) != 32 or len(secret) < 40 or any(c not in "0123456789abcdef" for c in token_id):
                raise ValueError("Invalid token")
            application = None
            if purpose == "application":
                # Revoke/reconnect lock the grant before credentials. Keep that order even when
                # last-use writes are throttled, including repeated authentication in one unit.
                application = (
                    await self.applications.find_by_id(application_id, lock=LockMode.PESSIMISTIC_WRITE)
                    if self.applications
                    else None
                )
            row = await self.repository.find_by_id(token_id)
            if row is None or row.purpose != purpose:
                raise ValueError("Invalid token")
            if purpose == "application" and (
                row.authorized_application_id != application_id
                or not credential_matches(application, row, datetime.now(UTC))
            ):
                raise ValueError("Invalid application credential")
            valid = hmac.compare_digest(row.token_hash, hashlib.sha256(token.encode()).hexdigest())
            if not valid or row.revoked_at is not None or row.expires_at <= datetime.now(UTC):
                raise ValueError("Invalid token")
            issuer, separator, subject = row.subject.partition("|")
            if not separator or not issuer or not subject:
                raise ValueError("Invalid identity")
        except ValueError as exc:
            raise UnauthorizedException("The API token is invalid or expired", code="INVALID_TOKEN") from exc
        context = SecurityContext(
            user_id=subject, attributes={"iss": issuer, "sub": subject, "koinon_token_id": row.id}
        )
        context.attributes["koinon_token"] = cast(
            Any,
            {
                "id": row.id,
                "scopes": row.scopes,
                "tenant_id": row.tenant_id,
                "workspace_ids": row.workspace_ids,
                "asset_ids": row.asset_ids,
                "purpose": row.purpose,
                "authorized_application_id": row.authorized_application_id,
            },
        )
        if row.last_used_at is None or row.last_used_at < datetime.now(UTC) - timedelta(minutes=5):
            await self.repository.touch(row.id)
        if purpose == "application" and self.applications is not None:
            await self.applications.touch(application_id)
        return context

    @transactional
    async def revoke(self, subject: str, token_id: str):
        row = await self.repository.find_by_id(token_id, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.subject != subject or row.purpose != "personal":
            raise AccessDenied("This token is unavailable", code="ACCESS_DENIED")
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            await self.repository.save(row)
            await self.catalog._audit(subject, row.tenant_id, "token.revoked", row.id)

    async def scope_options(self, subject: str, tenant_id: str, workspace_id: str | None = None) -> dict:
        await self.catalog.authorize(subject, tenant_id, "catalog:read", workspace_id)
        allowed = set(await self.catalog.permissions(subject, tenant_id, workspace_id)) | PERSONAL_SCOPES
        labels = {
            "catalog:read": "Browse knowledge",
            "catalog:write": "Maintain knowledge",
            "knowledge:search": "Search documents",
            "query:execute": "Query datasets",
            "chat:use": "Use agents and chat",
            "ingest:write": "Import knowledge",
            "providers:write": "Manage model providers",
            "agents:write": "Configure agents",
            "jobs:manage": "Manage processing jobs",
            "sources:configure": "Configure sources",
            "indexes:manage": "Manage indexes",
            "audit:read": "Read audit records",
            "members:write": "Manage people and access",
            "settings:write": "Manage organization settings",
            "identity:manage": "Manage identity policy",
            "exports:read": "Download authorized exports",
            "exports:write": "Create authorized exports",
            "shares:read": "Read authenticated conversation shares",
            "shares:write": "Create and revoke your conversation shares",
            "evidence:read": "Inspect answer sources",
            "profile:read": "Read your profile",
            "profile:write": "Update your profile",
        }
        return {
            "items": [
                {
                    "id": scope,
                    "name": labels.get(scope, scope),
                    "dependencies": sorted(DEPENDENCIES.get(scope, ())),
                }
                for scope in sorted(allowed)
            ],
            "max_lifetime_days": self.settings.max_lifetime_days,
            "max_active_per_user": self.settings.max_active_per_user,
        }
