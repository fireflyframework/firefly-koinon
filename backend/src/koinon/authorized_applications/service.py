# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from uuid import uuid4

from pyfly.container import service
from pyfly.data import transactional
from pyfly.data.relational.sqlalchemy import LockMode
from pyfly.kernel import InvalidRequestException, ResourceNotFoundException
from sqlalchemy import select, update

from koinon.authorized_applications.dtos import application_dto
from koinon.authorized_applications.entities import AuthorizedApplication
from koinon.authorized_applications.repositories import AuthorizedApplicationRepository
from koinon.catalog.service import CatalogService
from koinon.profiles.service import ProfileService
from koinon.tokens.entities import PersonalToken
from koinon.tokens.service import PersonalTokenService
from koinon.tokens.settings import TokenSettings
from koinon.web.pagination import sql_page


@service(name="authorized_applications.service")
class AuthorizedApplicationService:
    def __init__(
        self,
        repository: AuthorizedApplicationRepository,
        tokens: PersonalTokenService,
        profiles: ProfileService,
        catalog: CatalogService,
        settings: TokenSettings,
    ):
        self.repository, self.tokens, self.profiles = repository, tokens, profiles
        self.catalog, self.settings = catalog, settings

    @transactional(read_only=True)
    async def page(
        self, subject: str, *, q="", status="all", page=1, page_size=25, sort="connected_at", order="desc"
    ) -> dict:
        if status not in {"all", "active", "expired", "revoked"}:
            raise InvalidRequestException("Choose a supported application status", code="INVALID_FILTER")
        predicates = [AuthorizedApplication.subject == subject]
        now = datetime.now(UTC)
        if status in {"active", "expired"}:
            predicates += [
                AuthorizedApplication.revoked_at.is_(None),
                AuthorizedApplication.expires_at > now
                if status == "active"
                else AuthorizedApplication.expires_at <= now,
            ]
        elif status == "revoked":
            predicates.append(AuthorizedApplication.revoked_at.is_not(None))
        result = await sql_page(
            AuthorizedApplication,
            predicates,
            q=q,
            page=page,
            page_size=page_size,
            sort=sort,
            order=order,
            sorts=("name", "connected_at", "expires_at", "last_used_at"),
            search=("name", "client_id", "tenant_name", "workspace_name"),
        )
        return {**result, "items": [application_dto(row) for row in result["items"]]}

    async def _owned(self, subject, identifier, *, lock=None):
        row = await self.repository.find_by_id(identifier, **({"lock": lock} if lock else {}))
        if row is None or row.subject != subject:
            raise ResourceNotFoundException(
                "This application connection is unavailable", code="APPLICATION_UNAVAILABLE"
            )
        return row

    @transactional(read_only=True)
    async def detail(self, subject: str, identifier: str) -> dict:
        return application_dto(await self._owned(subject, identifier))

    @transactional
    async def issue(
        self,
        subject,
        *,
        client_id,
        name,
        resource,
        tenant_id,
        tenant_name,
        workspace_id,
        workspace_name,
        scopes,
        expires_at,
    ):
        await self.profiles.lock_owner(subject)
        prior = list(
            (
                await self.repository._require_session().scalars(
                    select(AuthorizedApplication)
                    .where(
                        AuthorizedApplication.subject == subject,
                        AuthorizedApplication.client_id == client_id,
                        AuthorizedApplication.resource == resource,
                        AuthorizedApplication.tenant_id == tenant_id,
                        AuthorizedApplication.workspace_id == workspace_id,
                        AuthorizedApplication.revoked_at.is_(None),
                        AuthorizedApplication.expires_at > datetime.now(UTC),
                    )
                    .with_for_update()
                )
            ).all()
        )
        for previous in prior:
            await self._revoke(previous, "application.replaced")
        if await self.repository.active_count(subject) >= self.settings.max_active_applications_per_user:
            raise InvalidRequestException(
                "Disconnect an application before connecting another", code="APPLICATION_LIMIT_REACHED"
            )
        row = await self.repository.save(
            AuthorizedApplication(
                id=uuid4().hex,
                subject=subject,
                client_id=client_id,
                name=name,
                resource=resource,
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                scopes=sorted(set(scopes)),
                connected_at=datetime.now(UTC),
                expires_at=expires_at,
            )
        )
        credential = await self.tokens.issue_application(
            subject,
            {
                "name": name,
                "tenant_id": tenant_id,
                "workspace_ids": [workspace_id],
                "scopes": row.scopes,
                "expires_at": expires_at,
            },
            row.id,
        )
        await self.catalog._audit(
            subject,
            tenant_id,
            "application.connected",
            row.id,
            {"client_id": client_id, "scopes": row.scopes},
        )
        return row, credential

    @transactional
    async def revoke(self, subject: str, identifier: str):
        row = await self._owned(subject, identifier, lock=LockMode.PESSIMISTIC_WRITE)
        await self._revoke(row, "application.revoked")

    async def _revoke(self, row, action):
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            await self.repository.save(row)
            await self.tokens.repository._require_session().execute(
                update(PersonalToken)
                .where(PersonalToken.authorized_application_id == row.id, PersonalToken.revoked_at.is_(None))
                .values(revoked_at=row.revoked_at)
            )
            await self.catalog._audit(row.subject, row.tenant_id, action, row.id)
