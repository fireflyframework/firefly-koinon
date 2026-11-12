# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.kernel import InvalidRequestException
from sqlalchemy import func, select

from koinon.evidence.entities import EvidenceReview
from koinon.exports.entities import ExportRecord
from koinon.integrations.content_sources.read_classification import local_saved_evidence


@repository(name="exports.repository")
class KnowledgeExportRepository(Repository[ExportRecord, str]):
    def _statement(self, subject, tenant_id, *, q="", status="all", local_only=False):
        if len(q) > 512 or status not in {"all", "ready", "cancelled", "expired"}:
            raise InvalidRequestException("Choose valid export filters", code="INVALID_PAGE")
        predicates = [ExportRecord.owner_subject == subject, ExportRecord.tenant_id == tenant_id]
        now = datetime.now(UTC)
        if status == "cancelled":
            predicates.append(ExportRecord.cancelled_at.is_not(None))
        elif status in {"ready", "expired"}:
            predicates.extend(
                [
                    ExportRecord.cancelled_at.is_(None),
                    ExportRecord.expires_at > now if status == "ready" else ExportRecord.expires_at <= now,
                ]
            )
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = select(ExportRecord).join(EvidenceReview).where(*predicates)
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
            raise InvalidRequestException("Choose valid export filters", code="INVALID_PAGE")
        statement = self._statement(subject, tenant_id, q=q, status=status, local_only=True)
        session = self._require_session()
        total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        rows = list(
            await session.scalars(
                statement.order_by(ExportRecord.created_at.desc(), ExportRecord.id)
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
        statement = self._statement(subject, tenant_id, status="ready")
        return int(
            await self._require_session().scalar(select(func.count()).select_from(statement.subquery())) or 0
        )

    async def scan(self, subject, tenant_id, *, status, position, page_size, local_only=False):
        if not 1 <= position <= 1000000 or not 1 <= page_size <= 100:
            raise InvalidRequestException("Choose valid export filters", code="INVALID_PAGE")
        statement = self._statement(subject, tenant_id, status=status, local_only=local_only)
        return list(
            await self._require_session().scalars(
                statement.with_only_columns(ExportRecord.id)
                .order_by(ExportRecord.created_at.desc(), ExportRecord.id)
                .offset((position - 1) * page_size)
                .limit(page_size)
            )
        )
