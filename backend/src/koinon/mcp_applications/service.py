# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import secrets
from datetime import UTC, datetime
from uuid import uuid4

from cryptography.fernet import Fernet
from pyfly.container import service
from pyfly.data import transactional
from pyfly.data.relational.sqlalchemy import LockMode
from pyfly.kernel import ConflictException, InvalidRequestException
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import select, update

from koinon.authorized_applications.entities import AuthorizedApplication
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.communications.ports import AccountEventRecorder
from koinon.mcp.settings import McpSettings
from koinon.mcp_applications.dtos import (
    McpOAuthClient,
    McpOAuthClientCredential,
    McpOAuthClientInput,
    McpOAuthClientPatch,
    McpOAuthClientReadiness,
    McpOAuthClientValues,
)
from koinon.mcp_applications.entities import McpOAuthClientRegistration
from koinon.mcp_applications.repositories import McpOAuthClientRepository
from koinon.mcp_auth.settings import McpOAuthSettings
from koinon.security.authority import primary_authority
from koinon.tokens.entities import PersonalToken
from koinon.web.pagination import sql_page


def client_dto(row) -> McpOAuthClient:
    return McpOAuthClient.model_validate({key: getattr(row, key) for key in McpOAuthClient.model_fields})


@service(name="mcp.applications.registry")
class McpOAuthClientRegistry:
    def __init__(
        self,
        repository: McpOAuthClientRepository,
        catalog: CatalogService,
        settings: McpOAuthSettings,
        mcp: McpSettings,
        events: AccountEventRecorder | None = None,
    ):
        self.repository, self.catalog, self.settings, self.mcp = repository, catalog, settings, mcp
        self.events = events

    async def _authorize(self, actor, tenant_id):
        context = SecurityContextHolder.get_context()
        if context and ("koinon_token" in context.attributes or "koinon_token_id" in context.attributes):
            raise AccessDenied(
                "Manage OAuth applications through your user identity.",
                code="INTERACTIVE_IDENTITY_REQUIRED",
            )
        await self.catalog.authorize(actor, tenant_id, "identity:manage")

    async def _row(self, tenant_id, identifier, *, lock=False):
        row = await self.repository.find_by_id(
            identifier, **({"lock": LockMode.PESSIMISTIC_WRITE} if lock else {})
        )
        if row is None or row.tenant_id != tenant_id:
            raise AccessDenied("OAuth application is unavailable in this organization.", code="ACCESS_DENIED")
        return row

    @primary_authority()
    async def readiness(self, actor, tenant_id) -> McpOAuthClientReadiness:
        await self._authorize(actor, tenant_id)
        missing = []
        if not self.mcp.enabled:
            missing.append("mcp_endpoint")
        if not self.settings.enabled:
            missing.append("oauth_enabled")
        try:
            Fernet(self.settings.encryption_key.encode("ascii"))
            configured = True
        except (ValueError, UnicodeError, AttributeError):
            configured = False
        if not configured:
            missing.append("oauth_encryption_key")
        return McpOAuthClientReadiness(
            ready=not missing,
            endpoint_enabled=self.mcp.enabled,
            oauth_enabled=self.settings.enabled,
            encryption_configured=configured,
            missing_configuration=missing,
        )

    @primary_authority()
    async def page(
        self, actor, tenant_id, *, q="", status="all", page=1, page_size=25, sort="name", order="asc"
    ):
        await self._authorize(actor, tenant_id)
        if status not in {"all", "enabled", "disabled"}:
            raise InvalidRequestException("Choose a supported application status", code="INVALID_FILTER")
        predicates = [McpOAuthClientRegistration.tenant_id == tenant_id]
        if status != "all":
            predicates.append(McpOAuthClientRegistration.enabled == (status == "enabled"))
        result = await sql_page(
            McpOAuthClientRegistration,
            predicates,
            q=q,
            page=page,
            page_size=page_size,
            search=("name", "client_id"),
            sort=sort,
            sorts=("name", "updated_at"),
            order=order,
        )
        return {**result, "items": [client_dto(row).model_dump(mode="json") for row in result["items"]]}

    @primary_authority()
    async def get(self, actor, tenant_id, identifier) -> McpOAuthClient:
        await self._authorize(actor, tenant_id)
        return client_dto(await self._row(tenant_id, identifier))

    @transactional
    async def create(self, actor, tenant_id, body: McpOAuthClientInput) -> McpOAuthClientCredential:
        await self.catalog._lock_tenant(tenant_id)
        await self._authorize(actor, tenant_id)
        identifier, client_id = str(uuid4()), "koinon_org_" + uuid4().hex
        if any(value["client_id"] == client_id for value in self.settings.clients):
            raise ConflictException("OAuth client identifier is already registered", code="CLIENT_EXISTS")
        secret = secrets.token_urlsafe(48) if body.client_type == "confidential" else None
        now = datetime.now(UTC)
        row = await self.repository.save(
            McpOAuthClientRegistration(
                id=identifier,
                tenant_id=tenant_id,
                client_id=client_id,
                name=body.name,
                client_type=body.client_type,
                redirect_uris=body.redirect_uris,
                scopes=body.scopes,
                client_secret_hash=hashlib.sha256(secret.encode()).hexdigest() if secret else None,
                enabled=True,
                revision=1,
                created_by=actor,
                updated_by=actor,
                created_at=now,
                updated_at=now,
            )
        )
        await self.catalog._audit(actor, tenant_id, "mcp.client.created", identifier, {"revision": 1})
        if self.events is not None:
            await self.events.security_changed(
                actor, actor, tenant_id, "client_registered", row.id, row.name, scopes=row.scopes
            )
        return McpOAuthClientCredential(client=client_dto(row), client_secret=secret)

    @transactional
    async def update(self, actor, tenant_id, identifier, body: McpOAuthClientPatch) -> McpOAuthClient:
        await self.catalog._lock_tenant(tenant_id)
        await self._authorize(actor, tenant_id)
        row = await self._row(tenant_id, identifier, lock=True)
        self._revision(row, body.expected_revision)
        changes = body.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if not changes or any(value is None for value in changes.values()):
            raise InvalidRequestException("Supply application fields to update", code="INVALID_CLIENT")
        merged = McpOAuthClientValues.model_validate(
            {key: changes.get(key, getattr(row, key)) for key in McpOAuthClientValues.model_fields}
        )
        for key, value in merged.model_dump().items():
            setattr(row, key, value)
        if "enabled" in changes:
            row.enabled = changes["enabled"]
        await self._changed(row, actor, "mcp.client.updated")
        return client_dto(row)

    @transactional
    async def rotate_secret(
        self, actor, tenant_id, identifier, expected_revision
    ) -> McpOAuthClientCredential:
        await self.catalog._lock_tenant(tenant_id)
        await self._authorize(actor, tenant_id)
        row = await self._row(tenant_id, identifier, lock=True)
        self._revision(row, expected_revision)
        if row.client_type != "confidential":
            raise InvalidRequestException(
                "Public applications do not have client secrets", code="INVALID_CLIENT"
            )
        secret = secrets.token_urlsafe(48)
        row.client_secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        await self._changed(row, actor, "mcp.client.secret_rotated")
        return McpOAuthClientCredential(client=client_dto(row), client_secret=secret)

    @staticmethod
    def _revision(row, expected):
        if type(expected) is not int or row.revision != expected or row.revision >= 2147483647:
            raise ConflictException(
                "This OAuth application changed. Reload and try again.", code="CLIENT_REVISION_CONFLICT"
            )

    async def _changed(self, row, actor, action):
        row.revision += 1
        row.updated_by, row.updated_at = actor, datetime.now(UTC)
        await self.repository.save(row)
        session = self.repository._require_session()
        applications = select(AuthorizedApplication.id).where(
            AuthorizedApplication.client_id == row.client_id,
            AuthorizedApplication.tenant_id == row.tenant_id,
        )
        await session.execute(
            update(AuthorizedApplication)
            .where(AuthorizedApplication.id.in_(applications), AuthorizedApplication.revoked_at.is_(None))
            .values(revoked_at=row.updated_at)
        )
        await session.execute(
            update(PersonalToken)
            .where(
                PersonalToken.authorized_application_id.in_(applications),
                PersonalToken.revoked_at.is_(None),
            )
            .values(revoked_at=row.updated_at)
        )
        await self.catalog._audit(actor, row.tenant_id, action, row.id, {"revision": row.revision})
        if self.events is not None:
            subtype = (
                "client_secret_rotated"
                if action == "mcp.client.secret_rotated"
                else "client_revoked"
                if not row.enabled
                else "client_changed"
            )
            await self.events.security_changed(
                actor, actor, row.tenant_id, subtype, row.id, row.name, scopes=row.scopes
            )
