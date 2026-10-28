# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.kernel import InvalidRequestException
from sqlalchemy import func, select

from koinon.evidence.entities import EvidenceReview
from koinon.sharing.entities import ConversationShare


@repository(name="sharing.repository")
class ConversationShareRepository(Repository[ConversationShare, str]):
    async def page(self, subject, tenant_id, *, q="", status="all", page=1, page_size=25):
        if (
            len(q) > 512
            or status not in {"all", "active", "revoked", "expired"}
            or page < 1
            or not 1 <= page_size <= 100
        ):
            raise InvalidRequestException("Choose valid share filters", code="INVALID_PAGE")
        predicates = [ConversationShare.owner_subject == subject, ConversationShare.tenant_id == tenant_id]
        now = datetime.now(UTC)
        if status == "revoked":
            predicates.append(ConversationShare.revoked_at.is_not(None))
        elif status in {"active", "expired"}:
            predicates.extend(
                [
                    ConversationShare.revoked_at.is_(None),
                    ConversationShare.expires_at > now
                    if status == "active"
                    else ConversationShare.expires_at <= now,
                ]
            )
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = select(ConversationShare).join(EvidenceReview).where(*predicates)
        if escaped:
            statement = statement.where(EvidenceReview.title.ilike("%" + escaped + "%", escape="\\"))
        session = self._require_session()
        total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        rows = list(
            await session.scalars(
                statement.order_by(ConversationShare.created_at.desc(), ConversationShare.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    async def active_count(self, subject, tenant_id):
        page = await self.page(subject, tenant_id, status="active", page_size=1)
        return page["total"]
