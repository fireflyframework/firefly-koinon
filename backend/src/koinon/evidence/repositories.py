# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, select

from koinon.evidence.entities import EvidenceReview


@repository(name="evidence.review_repository")
class EvidenceReviewRepository(Repository[EvidenceReview, str]):
    async def active_count(self, subject, tenant_id):
        return int(
            await self._require_session().scalar(
                select(func.count())
                .select_from(EvidenceReview)
                .where(
                    EvidenceReview.owner_subject == subject,
                    EvidenceReview.tenant_id == tenant_id,
                    EvidenceReview.expires_at > datetime.now(UTC),
                    EvidenceReview.consumed_at.is_(None),
                )
            )
            or 0
        )
