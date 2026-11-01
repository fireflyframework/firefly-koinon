# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import base64
import re
import unicodedata
from contextlib import suppress
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import InvalidRequestException, ResourceNotFoundException
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.corporate_profiles.mappers import author_view
from koinon.corporate_profiles.projector import CorporateProfileProjector
from koinon.profiles.dtos import PersonOutput
from koinon.profiles.entities import Profile
from koinon.profiles.images import sanitize_avatar
from koinon.profiles.mappers import profile_dto, system_author
from koinon.profiles.repositories import ProfileRepository
from koinon.security.authority import primary_authority

FIELDS = frozenset({"display_name", "locale", "time_zone", "response_language"})


def profile_id(subject: str) -> str:
    if not isinstance(subject, str) or not 1 < len(subject) <= 512 or "|" not in subject:
        raise ValueError("A canonical verified subject is required")
    return sha256(subject.encode()).hexdigest()


def language_tag(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 64
        or not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", value)
    ):
        raise ValueError("Use a language tag such as en-US or es-MX")
    parts = value.split("-")
    result = [parts[0].lower()]
    extension = False
    for part in parts[1:]:
        if len(part) == 1:
            extension = True
        result.append(
            part.lower()
            if extension
            else part.upper()
            if len(part) == 2 and part.isalpha()
            else part.title()
            if len(part) == 4 and part.isalpha()
            else part.lower()
        )
    if len(parts[-1]) == 1:
        raise ValueError("A language extension requires a value")
    return "-".join(result)


def preferences(values: dict) -> dict:
    if set(values) - FIELDS:
        raise ValueError("Only personal presentation preferences may be changed")
    result = {}
    for key, value in values.items():
        if not isinstance(value, str):
            raise ValueError("Profile preferences must be strings")
        if key == "display_name":
            value = value.strip()
            if (
                not value
                or len(value) > 120
                or any(unicodedata.category(char) in {"Cc", "Cs"} for char in value)
            ):
                raise ValueError("Display name must contain 1 to 120 printable characters")
        elif key == "time_zone":
            if len(value) > 64:
                raise ValueError("Choose an IANA timezone")
            try:
                ZoneInfo(value)
            except (ValueError, ZoneInfoNotFoundError) as exc:
                raise ValueError("Choose an IANA timezone") from exc
        elif key == "response_language" and value == "auto":
            pass
        else:
            value = language_tag(value)
        result[key] = value
    return result


@service(name="profiles.service")
class ProfileService:
    def __init__(
        self,
        profiles: ProfileRepository,
        catalog: CatalogService,
        presentation: CorporateProfileProjector | None = None,
    ):
        self.presentation = presentation
        self.profiles, self.catalog = profiles, catalog
        self._image_slots = asyncio.Semaphore(2)

    def _defaults(self, subject: str, verified: dict | None = None) -> Profile:
        values = {"display_name": "", "locale": "en-US", "time_zone": "UTC", "response_language": "auto"}
        for claim, key in (("name", "display_name"), ("locale", "locale")):
            if verified and isinstance(verified.get(claim), str):
                with suppress(ValueError):
                    values.update(preferences({key: verified[claim]}))
        return Profile(id=profile_id(subject), subject=subject, **values)

    async def get(self, subject: str, verified: dict | None = None) -> dict:
        row = await self.profiles.find_by_id(profile_id(subject))
        if row is None and verified is not None:
            row = await self._initialize(subject, verified)
        return profile_dto(row or self._defaults(subject, verified))

    @transactional
    async def _initialize(self, subject: str, verified: dict) -> Profile:
        return await self._locked(subject, verified)

    async def _locked(self, subject: str, verified: dict | None = None) -> Profile:
        unit = current_unit_of_work("primary")
        if unit is None:
            raise RuntimeError("Profile writes require the native primary transaction")
        session = unit.resource
        builder = sqlite_insert if session.bind.dialect.name == "sqlite" else pg_insert
        initial = self._defaults(subject, verified)
        await session.execute(
            builder(Profile)
            .values(
                id=profile_id(subject),
                subject=subject,
                display_name=initial.display_name,
                locale=initial.locale,
                time_zone=initial.time_zone,
                response_language=initial.response_language,
            )
            .on_conflict_do_nothing(index_elements=["subject"])
        )
        return await self.profiles.find_by_id(profile_id(subject), lock=LockMode.PESSIMISTIC_WRITE)

    @transactional
    async def lock_owner(self, subject: str) -> None:
        """Hold one canonical owner's row lock until the enclosing native transaction completes."""
        context = SecurityContextHolder.get_context()
        verified = None
        if context and f"{context.attributes.get('iss')}|{context.attributes.get('sub')}" == subject:
            verified = context.attributes
        await self._locked(subject, verified)

    @transactional
    async def update(self, subject: str, values: dict) -> dict:
        try:
            changes = preferences(values)
        except ValueError as error:
            raise InvalidRequestException(str(error), code="INVALID_PROFILE") from error
        row = await self._locked(subject)
        for key, value in changes.items():
            setattr(row, key, value)
        row.updated_at = datetime.now(UTC)
        return profile_dto(await self.profiles.save(row))

    async def set_avatar(self, subject: str, content: bytes) -> dict:
        try:
            async with self._image_slots:
                image = await asyncio.to_thread(sanitize_avatar, content)
        except ValueError as error:
            raise InvalidRequestException(str(error), code="INVALID_AVATAR") from error
        return await self._save_avatar(subject, image)

    @transactional
    async def _save_avatar(self, subject: str, image: bytes | None) -> dict:
        row = await self._locked(subject)
        row.avatar_bytes = image
        row.avatar_version = sha256(image).hexdigest() if image else None
        row.updated_at = datetime.now(UTC)
        return profile_dto(await self.profiles.save(row))

    async def delete_avatar(self, subject: str) -> dict:
        return await self._save_avatar(subject, None)

    async def avatar(self, subject: str) -> bytes:
        row = await self.profiles.find_by_id(profile_id(subject))
        if row is None or not row.avatar_bytes:
            raise ResourceNotFoundException("Avatar is unavailable", code="AVATAR_NOT_FOUND")
        return row.avatar_bytes

    async def author_summary(self, subject: str) -> dict:
        row = await self.profiles.find_by_id(profile_id(subject)) if "|" in subject else None
        return self._author_summary(subject, row)

    async def author_summaries(
        self, subjects: set[str], *, actor=None, tenant_id=None, workspace_id=None, permission="catalog:read"
    ) -> dict[str, dict]:
        if not subjects:
            return {}
        rows = await self.profiles.author_rows(subjects)
        by_subject = {row.subject: row for row in rows}
        result = {
            subject: self._author_summary(subject, by_subject.get(subject)) for subject in sorted(subjects)
        }
        if self.presentation is not None and actor is not None and tenant_id is not None:
            # At most two authors per entry on a bounded 100-entry catalog page.
            wanted = set(subjects)
            result = {subject: self._author_summary(subject, None) for subject in subjects}
            projected = await self.presentation.batch(
                actor, tenant_id, wanted, workspace_id, authors=True, author_permission=permission
            )
            for subject, value in projected.items():
                result[subject] = author_view(value)
        for subject in subjects:
            if system := system_author(subject):
                result[subject] = system
        return result

    @staticmethod
    def _author_summary(subject: str, row: Profile | None) -> dict:
        return {
            "subject": subject,
            "display_name": row.display_name if row else "",
            "avatar_data_url": ("data:image/jpeg;base64," + base64.b64encode(row.avatar_bytes).decode())
            if row and row.avatar_bytes
            else None,
            "avatar_version": row.avatar_version if row else None,
        }

    @primary_authority()
    async def people(
        self,
        actor: str,
        tenant_id: str,
        *,
        workspace_id: str | None = None,
        q: str = "",
        limit: int = 20,
        after: str = "",
    ) -> dict:
        await self.catalog.authorize(actor, tenant_id, "members:write", workspace_id)
        if not isinstance(limit, int) or not 1 <= limit <= 50 or len(q) > 80 or len(after) > 512:
            raise InvalidRequestException(
                "Directory filters exceed the supported bounds", code="INVALID_DIRECTORY"
            )
        rows = await self.profiles.people_rows(
            self.catalog.effective_membership_rows(), tenant_id, workspace_id, q, after, limit
        )
        projected = None
        if self.presentation is not None:
            projected = await self.presentation.batch(
                actor,
                tenant_id,
                {subject for subject, _ in rows[:limit]},
                workspace_id,
                authors=True,
                author_permission="members:write",
            )
            if any(
                subject not in projected or not projected[subject].current_member
                for subject, _ in rows[:limit]
            ):
                raise AccessDenied("Person is unavailable in this directory", code="ACCESS_DENIED")
        items = []
        for subject, row in rows[:limit]:
            item = projected[subject] if projected is not None else None
            version = item.avatar_version if item else row.avatar_version if row else None
            url = (
                f"/api/v1/tenants/{quote(tenant_id, safe='')}/people/{row.id}/avatar?v={version}"
                if row and version
                else None
            )
            if url and workspace_id:
                url += "&workspace_id=" + quote(workspace_id, safe="")
            items.append(
                PersonOutput(
                    profile_id=row.id if row else None,
                    subject=subject,
                    display_name=item.name if item else row.display_name if row else "",
                    avatar_url=url,
                    avatar_version=version,
                ).model_dump()
            )
        return {"items": items, "next_cursor": rows[limit - 1][0] if len(rows) > limit else None}

    async def directory_avatar(
        self, actor: str, tenant_id: str, identifier: str, *, workspace_id: str | None = None
    ) -> bytes:
        await self.catalog.authorize(actor, tenant_id, "members:write", workspace_id)
        row = await self.profiles.find_by_id(identifier)
        if row is None:
            raise AccessDenied("Person is unavailable in this directory", code="ACCESS_DENIED")
        members = [
            member for member in await self.catalog.memberships(row.subject) if member.tenant_id == tenant_id
        ]
        if not any(workspace_id is None or member.workspace_id in (None, workspace_id) for member in members):
            raise AccessDenied("Person is unavailable in this directory", code="ACCESS_DENIED")
        if self.presentation is not None:
            projected = await self.presentation.batch(
                actor, tenant_id, {row.subject}, workspace_id, authors=True, author_permission="members:write"
            )
            content = projected[row.subject].avatar if row.subject in projected else None
            if not content:
                raise ResourceNotFoundException("Avatar is unavailable", code="AVATAR_NOT_FOUND")
            return content
        return await self.avatar(row.subject)
