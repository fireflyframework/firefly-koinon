# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private origin reservations around existing intake identities, not another intake queue.

These primitives are not wired to native publication. Activation requires the same fence before
publication and all reader surfaces; recording a receipt afterward cannot provide that protection.
"""

import hashlib
import json
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select

from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.mapping_entities import (
    SourceMapping,
    SourceObject,
)
from koinon.integrations.content_sources.mapping_repository import SourceMappingRepository
from koinon.knowledge.bulk.entities import BulkBatch, BulkItem


@repository(name="content_sources.import_repository")
class SourceImportRepository(Repository[SourceImportAttempt, str]):
    async def _fence(
        self,
        tenant: str,
        mapping_id: str,
        revision: int,
        object_id: str,
        generation: int,
        connection_revision: int,
    ) -> tuple[SourceMapping, SourceObject] | None:
        session = self._require_session()
        mapping = await SourceMappingRepository(session=session).lock_active(
            tenant, mapping_id, revision, connection_revision
        )
        if mapping is None:
            return None
        item = await session.scalar(
            select(SourceObject)
            .where(
                SourceObject.id == object_id,
                SourceObject.tenant_id == tenant,
                SourceObject.mapping_id == mapping_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            item is None
            or item.generation != generation
            or item.mapping_revision != revision
            or item.state not in {"pending", "imported"}
            or not item.remote_version
        ):
            return None
        return mapping, item

    async def _intake(self, mapping: SourceMapping, item_id: str) -> BulkItem | None:
        session = self._require_session()
        batch = await session.scalar(
            select(BulkBatch)
            .join(BulkItem, BulkItem.batch_id == BulkBatch.id)
            .where(
                BulkItem.id == item_id,
                BulkBatch.tenant_id == mapping.tenant_id,
                BulkBatch.subject == mapping.owner,
            )
            .with_for_update(of=BulkBatch)
            .execution_options(populate_existing=True)
        )
        if (
            batch is None
            or batch.cancelled
            or batch.workspace_id != mapping.workspace_id
            or batch.project_id != mapping.project_id
            or batch.parent_id != mapping.parent_id
        ):
            return None
        return await session.scalar(
            select(BulkItem)
            .where(BulkItem.id == item_id, BulkItem.batch_id == batch.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def reserve(
        self,
        tenant: str,
        mapping_id: str,
        revision: int,
        object_id: str,
        generation: int,
        intake_item_id: str,
        *,
        connection_revision: int,
    ) -> SourceImportAttempt | None:
        fenced = await self._fence(tenant, mapping_id, revision, object_id, generation, connection_revision)
        if fenced is None:
            return None
        mapping, item = fenced
        session = self._require_session()
        attempt = await session.scalar(
            select(SourceImportAttempt)
            .where(
                SourceImportAttempt.tenant_id == tenant,
                SourceImportAttempt.object_id == object_id,
                SourceImportAttempt.generation == generation,
            )
            .execution_options(populate_existing=True)
        )
        intake = await self._intake(mapping, intake_item_id)
        if intake is None:
            return None
        if attempt is not None:
            return (
                attempt
                if (
                    attempt.intake_item_id == intake_item_id
                    and attempt.mapping_revision == revision
                    and attempt.source_id == intake.source_id
                    and attempt.asset_id == intake.asset_id
                    and attempt.sha256 == intake.sha256
                    and attempt.size_bytes == intake.size_bytes
                    and attempt.remote_version == item.remote_version
                )
                else None
            )
        if intake.status != "awaiting_upload" or intake.job_id is not None:
            return None
        if (
            await session.scalar(
                select(SourceImportAttempt.id).where(
                    SourceImportAttempt.intake_item_id == intake_item_id,
                )
            )
            is not None
        ):
            return None
        key = json.dumps([tenant, object_id, generation], separators=(",", ":"))
        attempt = SourceImportAttempt(
            id=hashlib.sha256(key.encode()).hexdigest(),
            tenant_id=tenant,
            mapping_id=mapping_id,
            mapping_revision=revision,
            object_id=object_id,
            generation=generation,
            intake_item_id=intake_item_id,
            provider=mapping.provider,
            external_subject=mapping.external_subject,
            external_tenant=mapping.external_tenant,
            drive_id=mapping.drive_id,
            remote_item_id=item.item_id,
            remote_version=item.remote_version,
            source_id=intake.source_id,
            asset_id=intake.asset_id,
            sha256=intake.sha256,
            size_bytes=intake.size_bytes,
        )
        session.add(attempt)
        await session.flush()
        return attempt

    async def record_commit(self, tenant: str, attempt_id: str, *, connection_revision: int) -> bool:
        session = self._require_session()
        attempt = await session.scalar(
            select(SourceImportAttempt)
            .where(
                SourceImportAttempt.id == attempt_id,
                SourceImportAttempt.tenant_id == tenant,
            )
            .execution_options(populate_existing=True)
        )
        if attempt is None:
            return False
        captured = (attempt.mapping_id, attempt.mapping_revision, attempt.object_id, attempt.generation)
        fenced = await self._fence(tenant, *captured, connection_revision)
        if fenced is None:
            return False
        attempt = await session.scalar(
            select(SourceImportAttempt)
            .where(SourceImportAttempt.id == attempt_id, SourceImportAttempt.tenant_id == tenant)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            attempt is None
            or (attempt.mapping_id, attempt.mapping_revision, attempt.object_id, attempt.generation)
            != captured
        ):
            return False
        mapping, item = fenced
        intake = await self._intake(mapping, attempt.intake_item_id)
        if intake is None or intake.status != "succeeded" or not intake.receipt_json:
            return False
        receipt = intake.receipt_json
        if (
            item.remote_version != attempt.remote_version
            or intake.source_id != attempt.source_id
            or intake.asset_id != attempt.asset_id
            or intake.sha256 != attempt.sha256
            or intake.size_bytes != attempt.size_bytes
            or receipt.get("sha256") != attempt.sha256
            or receipt.get("size_bytes") != attempt.size_bytes
            or receipt.get("native_workspace_id") != intake.native_workspace_id
            or receipt.get("native_asset_id") != intake.native_id
            or not intake.native_id
            or not receipt.get("native_source_id")
            or receipt.get("domain") != ("canon" if intake.mode == "document" else "structured")
            or not receipt.get("source_version_id" if intake.mode == "document" else "file_version_id")
        ):
            return False
        if attempt.receipt_json is not None:
            return attempt.receipt_json == receipt
        attempt.receipt_json = dict(receipt)
        attempt.committed_at = datetime.now(UTC)
        item.state = "imported"
        await session.flush()
        return True
