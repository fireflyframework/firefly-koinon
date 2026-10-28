# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded directory reads from configured provider origins; never follow token claim URLs."""

import asyncio
import re
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlsplit
from uuid import UUID

import jwt
from pyfly.client import HttpxClientAdapter
from pyfly.container import component
from pyfly.context.lifecycle import pre_destroy
from pyfly.kernel import ServiceUnavailableException
from pyfly.oauth2 import OAuth2Client, OAuth2Endpoints

from koinon.corporate_identity.dtos import (
    EntraCredential,
    EntraSettings,
    GoogleCredential,
    GoogleWorkspaceSettings,
    KeycloakCredential,
    KeycloakSettings,
    ProviderCredential,
    ProviderSettings,
)
from koinon.corporate_identity.policy import DirectorySnapshot
from koinon.corporate_identity.settings import IdentitySettings
from koinon.security.settings import _endpoint


def unavailable():
    return ServiceUnavailableException(
        "Corporate directory could not be verified. Check its read permissions and connection.",
        code="IDENTITY_DIRECTORY_UNVERIFIED",
    )


@component(name="identity.directory")
class NativeCorporateDirectory:
    def __init__(self, settings: IdentitySettings):
        self.settings = settings
        self.http = HttpxClientAdapter(timeout=timedelta(seconds=8), trust_env=False)

    @pre_destroy
    async def close(self):
        await self.http.stop()

    def keycloak_origin(self, issuer: str) -> tuple[str, str]:
        _endpoint(issuer)
        parsed = urlsplit(issuer)
        prefix, separator, realm = parsed.path.rpartition("/realms/")
        configured_origin = f"{parsed.scheme}://{parsed.netloc}"
        admitted = configured_origin in self.settings.allowed_provider_origins or (
            parsed.scheme == "https"
            and parsed.port in (None, 443)
            and parsed.hostname in self.settings.allowed_provider_hosts
        )
        if (
            not admitted
            or not separator
            or not realm
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", realm)
            or parsed.query
            or any(segment == ".." for segment in prefix.split("/"))
            or any(ord(c) < 33 for c in issuer)
            or "\\" in issuer
        ):
            raise unavailable()
        origin = f"{parsed.scheme}://{parsed.netloc}" + prefix
        return origin, realm

    async def _json(self, url: str, token: str, *, params=None):
        response = await self.http.request_bounded(
            "GET",
            url,
            max_response_bytes=524288,
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            params=params,
            follow_redirects=False,
        )
        if response.status_code != 200:
            raise unavailable()
        return response.json()

    async def acquire(self, settings: ProviderSettings, credential: ProviderCredential | None) -> str:
        if credential is None or settings.kind != credential.kind:
            raise unavailable()
        try:
            async with asyncio.timeout(10):
                if isinstance(settings, GoogleWorkspaceSettings) and isinstance(credential, GoogleCredential):
                    if (
                        not credential.service_account_email
                        or credential.private_key is None
                        or not credential.delegated_admin
                    ):
                        raise unavailable()
                    now = int(time.time())
                    assertion = jwt.encode(
                        {
                            "iss": credential.service_account_email,
                            "sub": credential.delegated_admin,
                            "aud": "https://oauth2.googleapis.com/token",
                            "iat": now,
                            "exp": now + 300,
                            "scope": "https://www.googleapis.com/auth/admin.directory.group.readonly "
                            "https://www.googleapis.com/auth/admin.directory.user.readonly",
                        },
                        credential.private_key.get_secret_value(),
                        algorithm="RS256",
                        headers={"kid": credential.private_key_id} if credential.private_key_id else None,
                    )
                    response = await self.http.request_bounded(
                        "POST",
                        "https://oauth2.googleapis.com/token",
                        max_response_bytes=65536,
                        data={
                            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                            "assertion": assertion,
                        },
                        headers={"Accept": "application/json"},
                        follow_redirects=False,
                    )
                    value = response.json() if response.status_code == 200 else {}
                    token = value.get("access_token")
                    if (
                        not isinstance(token, str)
                        or not token
                        or len(token) > 65536
                        or value.get("token_type", "").casefold() != "bearer"
                    ):
                        raise unavailable()
                    return token
                if isinstance(settings, KeycloakSettings) and isinstance(credential, KeycloakCredential):
                    self.keycloak_origin(settings.issuer)
                    endpoint = settings.issuer.rstrip("/") + "/protocol/openid-connect/token"
                    scopes = ()
                elif isinstance(settings, EntraSettings) and isinstance(credential, EntraCredential):
                    endpoint = f"https://login.microsoftonline.com/{settings.tenant_id}/oauth2/v2.0/token"
                    scopes = ("https://graph.microsoft.com/.default",)
                else:
                    raise unavailable()
                async with OAuth2Client(
                    settings.directory_client_id or settings.client_id,
                    OAuth2Endpoints(endpoint),
                    client_secret=(credential.directory_secret or credential.secret).get_secret_value(),
                    timeout=8,
                    max_response_bytes=65536,
                    allow_loopback_http=True,
                ) as oauth:
                    result = await oauth.client_credentials(
                        scopes=scopes, authentication="client_secret_post"
                    )
                    return result.access_token
        except Exception:
            raise unavailable() from None

    async def observe(
        self, settings: ProviderSettings, token: str, external_subject: str
    ) -> DirectorySnapshot:
        try:
            async with asyncio.timeout(12):
                groups = await self._membership_groups(settings, token, external_subject)
            now = datetime.now(UTC)
            return DirectorySnapshot(
                external_subject,
                frozenset(groups),
                True,
                now,
                now + timedelta(seconds=self.settings.snapshot_ttl_seconds),
            )
        except Exception:
            raise unavailable() from None

    async def _membership_groups(self, settings: ProviderSettings, token: str, subject: str) -> set[str]:
        if not isinstance(subject, str) or not 1 <= len(subject) <= 512:
            raise unavailable()
        selected: set[str] = set()
        if isinstance(settings, KeycloakSettings):
            if settings.membership_mode != "direct":
                raise unavailable()
            origin, realm = self.keycloak_origin(settings.issuer)
            root = f"{origin}/admin/realms/{realm}/users/{quote(subject, safe='')}"
            user = await self._json(root, token)
            if user.get("id") != subject or type(user.get("enabled")) is not bool:
                raise unavailable()
            if not user["enabled"]:
                return set()
            for page in range(100):
                rows = await self._json(
                    root + "/groups",
                    token,
                    params={"first": page * 100, "max": 100, "briefRepresentation": "false"},
                )
                self._add(selected, rows)
                if len(rows) < 100:
                    return selected
            raise unavailable()
        if isinstance(settings, EntraSettings):
            subject = str(UUID(subject))
            root = f"https://graph.microsoft.com/v1.0/users/{subject}"
            user = await self._json(root, token, params={"$select": "id,accountEnabled"})
            if user.get("id") != subject or type(user.get("accountEnabled")) is not bool:
                raise unavailable()
            if not user["accountEnabled"]:
                return set()
            relationship = "transitiveMemberOf" if settings.membership_mode == "transitive" else "memberOf"
            url = root + "/" + relationship + "/microsoft.graph.group"
            required_path = urlsplit(url).path
            for _ in range(100):
                page = await self._json(url, token)
                self._add(selected, page.get("value"))
                next_url = page.get("@odata.nextLink")
                if next_url is None:
                    return selected
                parsed = urlsplit(next_url) if isinstance(next_url, str) else None
                if (
                    parsed is None
                    or len(next_url) > 8192
                    or parsed.scheme != "https"
                    or parsed.netloc != "graph.microsoft.com"
                    or parsed.path != required_path
                    or parsed.fragment
                    or parsed.username
                    or parsed.password
                ):
                    raise unavailable()
                url = next_url
            raise unavailable()
        if settings.membership_mode != "direct":
            raise unavailable()
        root = "https://admin.googleapis.com/admin/directory/v1"
        user = await self._json(root + "/users/" + quote(subject, safe=""), token)
        if user.get("id") != subject or type(user.get("suspended")) is not bool:
            raise unavailable()
        if user["suspended"]:
            return set()
        cursor = None
        for _ in range(100):
            params = {"userKey": subject, "maxResults": 100}
            if cursor:
                params["pageToken"] = cursor
            page = await self._json(root + "/groups", token, params=params)
            self._add(selected, page.get("groups", []))
            cursor = page.get("nextPageToken")
            if cursor is None:
                return selected
            if not isinstance(cursor, str) or not 1 <= len(cursor) <= 8192:
                raise unavailable()
        raise unavailable()

    @staticmethod
    def _add(selected: set[str], rows):
        if not isinstance(rows, list) or len(rows) > 1000:
            raise unavailable()
        for row in rows:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("id"), str)
                or not 1 <= len(row["id"]) <= 256
            ):
                raise unavailable()
            selected.add(row["id"])
        if len(selected) > 10000:
            raise unavailable()

    async def group(self, settings: ProviderSettings, token: str, identifier: str):
        if not 1 <= len(identifier) <= 256:
            raise unavailable()
        if isinstance(settings, KeycloakSettings):
            origin, realm = self.keycloak_origin(settings.issuer)
            url = f"{origin}/admin/realms/{realm}/groups/{quote(identifier, safe='')}"
        elif isinstance(settings, EntraSettings):
            url = f"https://graph.microsoft.com/v1.0/groups/{str(UUID(identifier))}"
        else:
            url = "https://admin.googleapis.com/admin/directory/v1/groups/" + quote(identifier, safe="")
        async with asyncio.timeout(10):
            row = await self._json(url, token)
        name = row.get("displayName", row.get("name"))
        if row.get("id") != identifier or not isinstance(name, str) or not 1 <= len(name) <= 255:
            raise unavailable()
        return {
            "id": identifier,
            "name": name,
            "path": row.get("path") if isinstance(row.get("path"), str) else None,
        }

    async def groups(self, settings: ProviderSettings, token: str, *, q="", limit=25, after=""):
        try:
            async with asyncio.timeout(12):
                return await self._groups(settings, token, q=q, limit=limit, after=after)
        except Exception:
            raise unavailable() from None

    async def _groups(self, settings: ProviderSettings, token: str, *, q="", limit=25, after=""):
        import base64

        if len(q) > 80 or not 1 <= limit <= 50 or len(after) > 16384 or any(ord(c) < 32 for c in q):
            raise unavailable()
        params = {}
        next_cursor = None
        if isinstance(settings, KeycloakSettings):
            origin, realm = self.keycloak_origin(settings.issuer)
            offset = int(after or "0")
            if not 0 <= offset <= 100000:
                raise unavailable()
            url = f"{origin}/admin/realms/{realm}/groups"
            params = {
                "search": q,
                "first": offset,
                "max": limit + 1,
                "briefRepresentation": "false",
                "populateHierarchy": "false",
            }
            value = await self._json(url, token, params=params)
            rows = value if isinstance(value, list) else None
            if isinstance(rows, list) and len(rows) > limit:
                next_cursor = str(offset + limit)
            rows = rows[:limit] if isinstance(rows, list) else rows
        elif isinstance(settings, EntraSettings):
            url = "https://graph.microsoft.com/v1.0/groups"
            params = {"$top": limit, "$select": "id,displayName"}
            if q:
                params["$filter"] = "startswith(displayName,'" + q.replace("'", "''") + "')"
            if after:
                url = base64.urlsafe_b64decode(after.encode()).decode()
                parts = urlsplit(url)
                if (
                    parts.scheme != "https"
                    or parts.netloc != "graph.microsoft.com"
                    or parts.path != "/v1.0/groups"
                    or parts.fragment
                ):
                    raise unavailable()
                params = None
            value = await self._json(url, token, params=params)
            rows = value.get("value") if isinstance(value, dict) else None
            following = value.get("@odata.nextLink") if isinstance(value, dict) else None
            if following:
                parts = urlsplit(following)
                if (
                    len(following) > 8192
                    or parts.scheme != "https"
                    or parts.netloc != "graph.microsoft.com"
                    or parts.path != "/v1.0/groups"
                    or parts.fragment
                ):
                    raise unavailable()
                next_cursor = base64.urlsafe_b64encode(following.encode()).decode()
        else:
            url = "https://admin.googleapis.com/admin/directory/v1/groups"
            params = {"maxResults": limit, "customer": settings.customer_id or "my_customer"}
            if q:
                literal = q.replace("\\", "\\\\").replace("'", "\\'").replace("*", "")
                params["query"] = "name:'" + literal + "'*"
            if after:
                params["pageToken"] = after
            value = await self._json(url, token, params=params)
            rows = value.get("groups", []) if isinstance(value, dict) else None
            next_cursor = value.get("nextPageToken") if isinstance(value, dict) else None
        if not isinstance(rows, list):
            raise unavailable()
        selected = set()
        self._add(selected, rows)
        if next_cursor is not None and (not isinstance(next_cursor, str) or len(next_cursor) > 16384):
            raise unavailable()
        items = []
        for row in rows:
            name = row.get("displayName", row.get("name"))
            if not isinstance(name, str) or not 1 <= len(name) <= 255:
                raise unavailable()
            items.append(
                {
                    "id": row["id"],
                    "name": name,
                    "path": row.get("path") if isinstance(row.get("path"), str) else None,
                    "membership_mode": settings.membership_mode,
                }
            )
        return {"items": items, "next_cursor": next_cursor}

    async def avatar(self, settings: ProviderSettings, token: str, subject: str) -> bytes | None:
        import base64

        if isinstance(settings, KeycloakSettings):
            return None
        if not 1 <= len(subject) <= 512:
            raise unavailable()
        async with asyncio.timeout(10):
            if isinstance(settings, EntraSettings):
                response = await self.http.request_bounded(
                    "GET",
                    f"https://graph.microsoft.com/v1.0/users/{str(UUID(subject))}/photo/$value",
                    headers={"Authorization": "Bearer " + token, "Accept": "image/*"},
                    max_response_bytes=2_097_152,
                    follow_redirects=False,
                )
                if response.status_code == 404:
                    return None
                if response.status_code != 200:
                    raise unavailable()
                return response.content
            response = await self.http.request_bounded(
                "GET",
                "https://admin.googleapis.com/admin/directory/v1/users/"
                + quote(subject, safe="")
                + "/photos/thumbnail",
                headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
                max_response_bytes=2_900_000,
                follow_redirects=False,
            )
            if response.status_code == 404:
                return None
            if response.status_code != 200:
                raise unavailable()
            value = response.json().get("photoData")
            if not isinstance(value, str) or len(value) > 2_800_000:
                raise unavailable()
            content = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
            if len(content) > 2_097_152:
                raise unavailable()
            return content
