# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read fixed directory APIs; configured Keycloak photos use an anonymous client."""

import asyncio
import base64
from datetime import timedelta
from urllib.parse import quote
from uuid import UUID

from pyfly.client import HttpxClientAdapter
from pyfly.container import component

from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.dtos import EntraSettings, GoogleWorkspaceSettings, KeycloakSettings
from koinon.corporate_profiles.normalization import FieldObservation, ProfileObservationError, normalize_user
from koinon.corporate_profiles.settings import CorporateProfileSettings


@component(name="corporate_profiles.directory")
class CorporateProfileDirectory:
    def __init__(self, directory: NativeCorporateDirectory, settings: CorporateProfileSettings):
        self.directory, self.settings = directory, settings

    async def _json(self, url, token, *, params=None):
        response = await self.directory.http.request_bounded(
            "GET",
            url,
            max_response_bytes=524288,
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            params=params,
            follow_redirects=False,
        )
        if response.status_code != 200:
            code = (
                "PROFILE_PERMISSION_DENIED"
                if response.status_code in (401, 403)
                else "PROFILE_USER_UNAVAILABLE"
                if response.status_code == 404
                else "PROFILE_RATE_LIMITED"
                if response.status_code == 429
                else "PROFILE_DIRECTORY_UNAVAILABLE"
            )
            raise ProfileObservationError(code)
        value = response.json()
        if not isinstance(value, dict):
            raise ProfileObservationError("PROFILE_RESPONSE_INVALID")
        return value

    async def observe(self, settings, credential, config, external_subject):
        try:
            async with asyncio.timeout(40):
                token = await self.directory.acquire(settings, credential)
                if isinstance(settings, EntraSettings):
                    url = f"https://graph.microsoft.com/v1.0/users/{str(UUID(external_subject))}"
                    raw = await self._json(
                        url, token, params={"$select": "id,accountEnabled,displayName,jobTitle,department"}
                    )
                elif isinstance(settings, GoogleWorkspaceSettings):
                    url = "https://admin.googleapis.com/admin/directory/v1/users/" + quote(
                        external_subject, safe=""
                    )
                    raw = await self._json(
                        url,
                        token,
                        params={
                            "projection": "full",
                            "viewType": "admin_view",
                            "fields": (
                                "id,customerId,suspended,archived,name/fullName,"
                                "organizations(title,department,primary),orgUnitPath,relations(type,value)"
                            ),
                        },
                    )
                elif isinstance(settings, KeycloakSettings):
                    origin, realm = self.directory.keycloak_origin(settings.issuer)
                    url = f"{origin}/admin/realms/{realm}/users/{quote(external_subject, safe='')}"
                    raw = await self._json(url, token)
                else:
                    raise ProfileObservationError("PROFILE_PROVIDER_UNSUPPORTED")
                result = normalize_user(settings, config, external_subject, raw)
                if (
                    isinstance(settings, GoogleWorkspaceSettings)
                    and config.manager_source == "directory"
                    and result.manager_lookup is not None
                ):
                    try:
                        manager = await self._json(
                            "https://admin.googleapis.com/admin/directory/v1/users/"
                            + quote(result.manager_lookup, safe=""),
                            token,
                            params={"fields": "id,customerId,suspended,archived"},
                        )
                        identifier = manager.get("id")
                        if (
                            not isinstance(identifier, str)
                            or not 1 <= len(identifier) <= 512
                            or manager.get("customerId") != result.customer_id
                            or manager.get("suspended") is not False
                            or manager.get("archived") is True
                        ):
                            raise ProfileObservationError("PROFILE_MANAGER_UNRESOLVED")
                        result.fields["manager"] = FieldObservation("current", identifier)
                    except Exception:
                        result.fields["manager"] = FieldObservation(
                            "unavailable", code="PROFILE_MANAGER_UNRESOLVED"
                        )
                if config.avatar_source == "directory":
                    try:
                        result.fields["avatar"] = await self._avatar(
                            settings, token, external_subject, result.fields.get("avatar")
                        )
                    except ProfileObservationError as error:
                        result.fields["avatar"] = FieldObservation("unavailable", code=error.code)
                    except Exception:
                        result.fields["avatar"] = FieldObservation(
                            "unavailable", code="PROFILE_PHOTO_INVALID"
                        )
                else:
                    result.fields["avatar"] = FieldObservation("not_observed")
                return result
        except ProfileObservationError:
            raise
        except Exception:
            raise ProfileObservationError() from None

    async def _avatar(self, settings, token, subject, selected):
        if isinstance(settings, KeycloakSettings):
            if selected is None or selected.status != "current":
                return selected or FieldObservation("unsupported", code="PROFILE_ATTRIBUTE_REQUIRED")
            if not self.settings.photo_url(selected.value):
                return FieldObservation("unavailable", code="PROFILE_PHOTO_ORIGIN_DENIED")
            client = HttpxClientAdapter(timeout=timedelta(seconds=8), trust_env=False, follow_redirects=False)
            try:
                response = await client.request_bounded(
                    "GET",
                    selected.value,
                    max_response_bytes=2097152,
                    headers={"Accept": "image/jpeg,image/png,image/webp"},
                    follow_redirects=False,
                )
            finally:
                await client.stop()
        elif isinstance(settings, EntraSettings):
            response = await self.directory.http.request_bounded(
                "GET",
                f"https://graph.microsoft.com/v1.0/users/{str(UUID(subject))}/photo/$value",
                max_response_bytes=2097152,
                headers={"Authorization": "Bearer " + token, "Accept": "image/jpeg,image/png,image/webp"},
                follow_redirects=False,
            )
        else:
            response = await self.directory.http.request_bounded(
                "GET",
                "https://admin.googleapis.com/admin/directory/v1/users/"
                + quote(subject, safe="")
                + "/photos/thumbnail",
                max_response_bytes=2900000,
                headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
                follow_redirects=False,
            )
        if response.status_code == 404:
            return FieldObservation("empty")
        if response.status_code != 200:
            return FieldObservation("unavailable", code="PROFILE_PHOTO_UNAVAILABLE")
        if isinstance(settings, GoogleWorkspaceSettings):
            value = response.json()
            if (
                not isinstance(value, dict)
                or value.get("id", subject) != subject
                or not isinstance(value.get("photoData"), str)
                or len(value["photoData"]) > 2800000
            ):
                return FieldObservation("unavailable", code="PROFILE_PHOTO_INVALID")
            content = base64.b64decode(
                value["photoData"] + "=" * (-len(value["photoData"]) % 4), altchars=b"-_", validate=True
            )
        else:
            content = response.content
        if not content or len(content) > 2097152:
            return FieldObservation("unavailable", code="PROFILE_PHOTO_INVALID")
        return FieldObservation("current", content)
