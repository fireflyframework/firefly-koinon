# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from pydantic import SecretStr
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import InvalidRequestException

from koinon.catalog.errors import AccessDenied
from koinon.catalog.invitation_dtos import InvitationCreated, InvitationInput, InvitationOutput
from koinon.catalog.invitation_entities import Invitation
from koinon.catalog.invitation_repository import InvitationRepository
from koinon.catalog.service import CatalogService


def invitation_dto(row: Invitation) -> dict:
    status = (
        "accepted"
        if row.accepted_at
        else "revoked"
        if row.revoked_at
        else "expired"
        if row.expires_at <= datetime.now(UTC)
        else "pending"
    )
    return InvitationOutput(
        **{
            field: getattr(row, field)
            for field in (
                "id",
                "tenant_id",
                "workspace_id",
                "role",
                "label",
                "created_by",
                "created_at",
                "expires_at",
                "accepted_at",
                "accepted_by",
            )
        },
        status=status,
    ).model_dump(mode="json")


def unavailable():
    return AccessDenied(
        "This invitation is unavailable. Ask an administrator for a new link.", code="INVITATION_UNAVAILABLE"
    )


@service(name="catalog.invitations")
class InvitationService:
    def __init__(self, invitations: InvitationRepository, catalog: CatalogService):
        self.invitations, self.catalog = invitations, catalog

    @transactional
    async def create(self, actor: str, tenant_id: str, **values) -> InvitationCreated:
        body = InvitationInput(**values)
        await self.catalog._lock_tenant(tenant_id)
        await self.catalog.authorize(actor, tenant_id, "members:write", body.workspace_id)
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        row = Invitation(
            id=str(uuid4()),
            tenant_id=tenant_id,
            workspace_id=body.workspace_id,
            role=body.role,
            label=body.label.strip(),
            token_hash=sha256(token.encode()).hexdigest(),
            created_by=actor,
            created_at=now,
            expires_at=now + timedelta(hours=body.expires_in_hours),
        )
        await self.invitations.save(row)
        await self.catalog._audit(
            actor,
            tenant_id,
            "invitation.created",
            row.id,
            {"role": row.role, "workspace_id": row.workspace_id},
        )
        return InvitationCreated(invitation=InvitationOutput(**invitation_dto(row)), token=SecretStr(token))

    @transactional(read_only=True)
    async def page(
        self, actor: str, tenant_id: str, *, workspace_id=None, status="pending", page=1, page_size=25
    ) -> dict:
        await self.catalog.authorize(actor, tenant_id, "members:write", workspace_id)
        if (
            status not in {"pending", "accepted", "revoked", "expired"}
            or page < 1
            or not 1 <= page_size <= 100
        ):
            raise InvalidRequestException(
                "Choose supported invitation filters", code="INVALID_INVITATION_FILTER"
            )
        result = await self.invitations.page(
            tenant_id, workspace_id=workspace_id, status=status, page=page, page_size=page_size
        )
        return {**result, "items": [invitation_dto(row) for row in result["items"]]}

    async def _available(self, actor: str, token: str, *, lock=False) -> Invitation:
        if not isinstance(token, str) or not 40 <= len(token) <= 128:
            raise unavailable()
        rows = await self.invitations.find_all(token_hash=sha256(token.encode()).hexdigest())
        if not rows:
            raise unavailable()
        row = rows[0]
        if lock:
            await self.catalog._lock_tenant(row.tenant_id)
            row = await self.invitations.find_by_id(row.id, lock=LockMode.PESSIMISTIC_WRITE)
        if (
            row is None
            or invitation_dto(row)["status"] != "pending"
            or actor.partition("|")[0] != row.created_by.partition("|")[0]
        ):
            raise unavailable()
        try:
            await self.catalog.authorize(row.created_by, row.tenant_id, "members:write", row.workspace_id)
        except AccessDenied as exc:
            raise unavailable() from exc
        if row.workspace_id:
            workspace = await self.catalog.get(row.created_by, row.tenant_id, row.workspace_id)
            if workspace.status == "archived":
                raise unavailable()
        return row

    @transactional(read_only=True)
    async def inspect(self, actor: str, token: str) -> dict:
        row = await self._available(actor, token)
        tenant = await self.catalog.tenant_repository.find_by_id(row.tenant_id)
        workspace = (
            await self.catalog.catalog_repository.find_by_id(row.workspace_id) if row.workspace_id else None
        )
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "tenant_name": tenant.name,
            "workspace_id": row.workspace_id,
            "workspace_name": workspace.name if workspace else None,
            "role": row.role,
            "expires_at": row.expires_at.isoformat(),
        }

    @transactional
    async def redeem(self, actor: str, token: str):
        row = await self._available(actor, token, lock=True)
        member = await self.catalog.create_member(
            row.created_by, row.tenant_id, subject=actor, role=row.role, workspace_id=row.workspace_id
        )
        row.accepted_at, row.accepted_by = datetime.now(UTC), actor
        await self.invitations.save(row)
        await self.catalog._audit(
            actor, row.tenant_id, "invitation.accepted", row.id, {"membership_id": member.id}
        )
        return member

    @transactional
    async def revoke(self, actor: str, tenant_id: str, identifier: str) -> None:
        await self.catalog._lock_tenant(tenant_id)
        row = await self.invitations.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.tenant_id != tenant_id:
            raise unavailable()
        await self.catalog.authorize(actor, tenant_id, "members:write", row.workspace_id)
        if row.accepted_at:
            raise InvalidRequestException(
                "Accepted invitations cannot be revoked. Remove the membership instead.",
                code="INVITATION_ACCEPTED",
            )
        if not row.revoked_at:
            row.revoked_at = datetime.now(UTC)
            await self.invitations.save(row)
            await self.catalog._audit(actor, tenant_id, "invitation.revoked", row.id)
