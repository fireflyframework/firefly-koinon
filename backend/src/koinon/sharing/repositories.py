# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.kernel import InvalidRequestException
from sqlalchemy import func, select

from koinon.evidence.entities import EvidenceReview
from koinon.integrations.content_sources.read_classification import local_saved_evidence
from koinon.sharing.entities import ConversationShare


@repository(name="sharing.repository")
class ConversationShareRepository(Repository[ConversationShare, str]):
    async def management_manifest(self, subject, tenant_id, review_id):
        return (
            await self._require_session().execute(
                select(EvidenceReview.manifest_json).where(
                    EvidenceReview.id == review_id,
                    EvidenceReview.tenant_id == tenant_id,
                    EvidenceReview.owner_subject == subject,
                    EvidenceReview.kind == "share",
                )
            )
        ).first()

    def _statement(self, subject, tenant_id, *, q="", status="all", local_only=False):
        if len(q) > 512 or status not in {"all", "active", "revoked", "expired"}:
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
        if local_only:
            session = self._require_session()
            statement = statement.where(
                local_saved_evidence(tenant_id, EvidenceReview, dialect=session.get_bind().dialect.name)
            )
        if escaped:
            statement = statement.where(EvidenceReview.title.ilike("%" + escaped + "%", escape="\\"))
        return statement

    async def page(self, subject, tenant_id, *, q="", status="all", page=1, page_size=25):
        if page < 1 or not 1 <= page_size <= 100:
            raise InvalidRequestException("Choose valid share filters", code="INVALID_PAGE")
        statement = self._statement(subject, tenant_id, q=q, status=status, local_only=True)
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
        statement = self._statement(subject, tenant_id, status="active")
        return int(
            await self._require_session().scalar(select(func.count()).select_from(statement.subquery())) or 0
        )

    async def scan(self, subject, tenant_id, *, status, position, page_size, local_only=False):
        if not 1 <= position <= 1000000 or not 1 <= page_size <= 100:
            raise InvalidRequestException("Choose valid share filters", code="INVALID_PAGE")
        statement = self._statement(subject, tenant_id, status=status, local_only=local_only)
        return list(
            await self._require_session().scalars(
                statement.with_only_columns(ConversationShare.id)
                .order_by(ConversationShare.created_at.desc(), ConversationShare.id)
                .offset((position - 1) * page_size)
                .limit(page_size)
            )
        )
