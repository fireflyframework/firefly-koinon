# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Provider-specific identity and delivery facts from fixed authoritative directory APIs."""

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import quote, urlsplit
from uuid import UUID

from pyfly.container import component
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ServiceUnavailableException

from koinon.communications.dtos import DeliveryAddressStatus
from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.dtos import EntraSettings, GoogleWorkspaceSettings, KeycloakSettings


def unavailable():
    return ServiceUnavailableException(
        "The intended directory account could not be verified", code="RECIPIENT_DIRECTORY_UNAVAILABLE"
    )


def delivery_address(value):
    if not isinstance(value, str) or not 3 <= len(value) <= 320 or value != value.strip():
        return None
    if not re.fullmatch(r"[^\s@<>\"(),;:\\]+@[^\s@<>\"(),;:\\/]+", value):
        return None
    local, domain = value.rsplit("@", 1)
    try:
        domain = domain.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None
    if (
        len(local) > 64
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", domain)
        or "." not in domain
        or ".." in domain
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        return None
    return local + "@" + domain


@dataclass(frozen=True, slots=True)
class DirectoryPerson:
    external_subject: str
    display_name: str
    email: str | None
    delivery_address_status: DeliveryAddressStatus
    reason: str | None = None


def normalize_recipient(settings, expected_subject, raw, *, allow_entra_guests=False) -> DirectoryPerson:
    if (
        not isinstance(expected_subject, str)
        or not 1 <= len(expected_subject) <= 512
        or not isinstance(raw, dict)
        or raw.get("id") != expected_subject
    ):
        raise unavailable()
    name = raw.get("displayName") or raw.get("username") or "Directory account"
    enabled, verified = False, False
    address = None
    if isinstance(settings, KeycloakSettings):
        enabled, verified = raw.get("enabled") is True, raw.get("emailVerified") is True
        address = raw.get("email")
        name = (
            " ".join(value for key in ("firstName", "lastName") if isinstance(value := raw.get(key), str))
            or name
        )
    elif isinstance(settings, EntraSettings):
        kind = raw.get("userType")
        enabled = raw.get("accountEnabled") is True and (
            kind == "Member" or kind == "Guest" and allow_entra_guests
        )
        verified = True
        address = raw.get("mail")
        if not address and kind == "Member":
            address = raw.get("userPrincipalName")
    elif isinstance(settings, GoogleWorkspaceSettings):
        address = raw.get("primaryEmail")
        parsed = delivery_address(address)
        domain = parsed.rpartition("@")[2] if parsed else None
        enabled = (
            raw.get("suspended") is False
            and raw.get("archived") is not True
            and (not settings.customer_id or raw.get("customerId") == settings.customer_id)
            and domain in settings.hosted_domains
        )
        verified = True
        name = raw.get("name", {}).get("fullName") if isinstance(raw.get("name"), dict) else name
    else:
        raise unavailable()
    name = name if isinstance(name, str) and name.strip() else "Directory account"
    name = name.strip()[:120]
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        name = "Directory account"
    parsed = delivery_address(address)
    if not enabled:
        return DirectoryPerson(expected_subject, name, None, "unavailable", "RECIPIENT_ACCOUNT_UNAVAILABLE")
    if address is None or address == "":
        return DirectoryPerson(expected_subject, name, None, "missing", "RECIPIENT_ADDRESS_MISSING")
    if parsed is None:
        return DirectoryPerson(expected_subject, name, None, "unavailable", "RECIPIENT_ADDRESS_INVALID")
    if not verified:
        return DirectoryPerson(expected_subject, name, None, "unverified", "RECIPIENT_ADDRESS_UNVERIFIED")
    return DirectoryPerson(expected_subject, name, parsed, "verified_directory")


@component(name="communications.recipient_directory")
class RecipientDirectory:
    def __init__(self, directory: NativeCorporateDirectory):
        self.directory = directory

    @staticmethod
    def _outside_transaction():
        if current_unit_of_work("primary") is not None:
            raise unavailable()

    def _root(self, settings):
        if isinstance(settings, EntraSettings):
            return "https://graph.microsoft.com/v1.0/users"
        if isinstance(settings, GoogleWorkspaceSettings):
            return "https://admin.googleapis.com/admin/directory/v1/users"
        if isinstance(settings, KeycloakSettings):
            origin, realm = self.directory.keycloak_origin(settings.issuer)
            return f"{origin}/admin/realms/{realm}/users"
        raise unavailable()

    @staticmethod
    def _fields(settings) -> dict[str, str | int]:
        if isinstance(settings, EntraSettings):
            return {"$select": "id,displayName,mail,userPrincipalName,accountEnabled,userType"}
        if isinstance(settings, GoogleWorkspaceSettings):
            return {"fields": "id,customerId,suspended,archived,primaryEmail,name/fullName"}
        return {}

    async def read(self, settings, credential, external_subject, *, allow_entra_guests=False):
        self._outside_transaction()
        try:
            if not isinstance(external_subject, str) or not 1 <= len(external_subject) <= 512:
                raise unavailable()
            if isinstance(settings, EntraSettings):
                external_subject = str(UUID(external_subject))
            async with asyncio.timeout(25):
                root = self._root(settings)
                token = await self.directory.acquire(settings, credential)
                raw = await self.directory._json(
                    root + "/" + quote(external_subject, safe=""), token, params=self._fields(settings)
                )
                return normalize_recipient(
                    settings, external_subject, raw, allow_entra_guests=allow_entra_guests
                )
        except Exception:
            raise unavailable() from None

    @staticmethod
    def _graph_cursor(value):
        parsed = urlsplit(value)
        if (
            len(value) > 8192
            or parsed.scheme != "https"
            or parsed.netloc != "graph.microsoft.com"
            or parsed.path != "/v1.0/users"
            or parsed.fragment
        ):
            raise unavailable()
        return value

    async def search(self, settings, credential, *, q, limit=20, after=None, allow_entra_guests=False):
        self._outside_transaction()
        try:
            if (
                not isinstance(q, str)
                or not 2 <= len(q.strip()) <= 80
                or any(ord(char) < 32 for char in q)
                or type(limit) is not int
                or not 1 <= limit <= 20
                or after is not None
                and (not isinstance(after, str) or len(after) > 8192)
            ):
                raise unavailable()
            async with asyncio.timeout(25):
                url = self._root(settings)
                params = self._fields(settings)
                if isinstance(settings, EntraSettings):
                    if after:
                        url, params = self._graph_cursor(after), None
                    else:
                        literal = q.replace("'", "''")
                        params.update(
                            {
                                "$top": limit,
                                "$filter": (
                                    f"startswith(displayName,'{literal}') "
                                    f"or startswith(userPrincipalName,'{literal}')"
                                ),
                            }
                        )
                elif isinstance(settings, GoogleWorkspaceSettings):
                    literal = q.replace("\\", "\\\\").replace("'", "\\'").replace("*", "")
                    params.update(
                        customer=settings.customer_id or "my_customer",
                        maxResults=limit,
                        query=f"name:'{literal}'*",
                    )
                    params["fields"] = (
                        "users(id,customerId,suspended,archived,primaryEmail,name/fullName),nextPageToken"
                    )
                    if after:
                        params["pageToken"] = after
                else:
                    offset = int(after or "0")
                    if not 0 <= offset <= 100000:
                        raise unavailable()
                    params.update(search=q, first=offset, max=limit + 1, briefRepresentation="false")
                token = await self.directory.acquire(settings, credential)
                raw = await self.directory._json(url, token, params=params)
                if isinstance(settings, EntraSettings):
                    rows, cursor = raw.get("value"), raw.get("@odata.nextLink")
                    if cursor is not None:
                        cursor = self._graph_cursor(cursor)
                elif isinstance(settings, GoogleWorkspaceSettings):
                    rows, cursor = raw.get("users", []), raw.get("nextPageToken")
                else:
                    rows = raw
                    cursor = str(offset + limit) if isinstance(rows, list) and len(rows) > limit else None
                maximum = limit + 1 if isinstance(settings, KeycloakSettings) else limit
                if not isinstance(rows, list) or len(rows) > maximum:
                    raise unavailable()
                if cursor is not None and (not isinstance(cursor, str) or not 1 <= len(cursor) <= 8192):
                    raise unavailable()
                people = [
                    normalize_recipient(settings, row.get("id"), row, allow_entra_guests=allow_entra_guests)
                    for row in rows[:limit]
                ]
                return people, cursor
        except Exception:
            raise unavailable() from None
