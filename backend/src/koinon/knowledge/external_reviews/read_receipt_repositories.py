# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, select

from koinon.knowledge.external_reviews.read_receipt_entities import ExternalReadReceiptRow


@repository(name="knowledge.external_reviews.read_receipts.repository")
class ExternalReadReceiptRepository(Repository[ExternalReadReceiptRow, str]):
    async def active_count(self, tenant_id, subject, now):
        return int(
            (
                await self._require_session().execute(
                    select(func.count())
                    .select_from(ExternalReadReceiptRow)
                    .where(
                        ExternalReadReceiptRow.tenant_id == tenant_id,
                        ExternalReadReceiptRow.subject == subject,
                        ExternalReadReceiptRow.expires_at > now,
                    )
                )
            ).scalar_one()
        )
