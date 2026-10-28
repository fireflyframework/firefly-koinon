# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, select

from koinon.catalog.invitation_entities import Invitation


@repository
class InvitationRepository(Repository[Invitation, str]):
    async def page(self, tenant_id, *, workspace_id=None, status="pending", page=1, page_size=25):
        now = datetime.now(UTC)
        filters = [Invitation.tenant_id == tenant_id]
        if workspace_id is not None:
            filters.append(Invitation.workspace_id == workspace_id)
        if status == "accepted":
            filters.append(Invitation.accepted_at.is_not(None))
        elif status == "revoked":
            filters.extend([Invitation.accepted_at.is_(None), Invitation.revoked_at.is_not(None)])
        elif status in {"pending", "expired"}:
            filters.extend([Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None)])
            filters.append(
                Invitation.expires_at > now if status == "pending" else Invitation.expires_at <= now
            )
        statement = select(Invitation).where(*filters)
        session = self._require_session()
        total = int((await session.scalar(select(func.count()).select_from(statement.subquery()))) or 0)
        rows = (
            await session.scalars(
                statement.order_by(Invitation.created_at.desc(), Invitation.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return {
            "items": list(rows),
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }
