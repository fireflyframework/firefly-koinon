# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, select

from koinon.knowledge.external_reviews.entities import ExternalFileReviewRow, ExternalReviewRow


@repository(name="knowledge.external_reviews.repository")
class ExternalReviewRepository(Repository[ExternalReviewRow, str]):
    pass


@repository(name="knowledge.external_reviews.files")
class ExternalFileReviewRepository(Repository[ExternalFileReviewRow, str]):
    async def staging_totals(self, tenant_id, subject):
        row = (
            await self._require_session().execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(ExternalFileReviewRow.request_json["size_bytes"].as_integer()), 0),
                ).where(
                    ExternalFileReviewRow.tenant_id == tenant_id,
                    ExternalFileReviewRow.subject == subject,
                    ExternalFileReviewRow.gc_status != "purged",
                    ExternalFileReviewRow.status.in_(
                        ["uploading", "preview", "cancelled", "ingesting", "unresolved"]
                    ),
                )
            )
        ).one()
        return int(row[0]), int(row[1])
