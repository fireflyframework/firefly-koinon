# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Canonical intake ports reuse native lineage receipts instead of replaying completed work."""

import json
from contextlib import asynccontextmanager
from dataclasses import asdict

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import Isolation, Propagation, transactional
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.knowledge.bulk.dataset_dtos import DatasetReservation
from koinon.knowledge.bulk.dataset_native import DatasetBulkNative
from koinon.knowledge.bulk.ports import BulkIntakePort, NativeCommit, NativeObservation
from koinon.knowledge.bulk.queue import BulkLease, BulkQueue
from koinon.knowledge.bulk.repositories import BulkRepository
from koinon.knowledge.service import KnowledgeFacade
from koinon.security.authority import PRIMARY_POLICY_UNIT


@service(name="knowledge.bulk.native_intake")
class NativeBulkIntake(BulkIntakePort):
    def __init__(self, facades: Provider[KnowledgeFacade | None], records: BulkRepository, queue: BulkQueue):
        self.facades, self.records, self.queue = facades, records, queue

    def facade(self) -> KnowledgeFacade:
        value = self.facades.get()
        if value is None:
            raise ServiceUnavailableException(
                "Canonical native intake is unavailable", code="BULK_NATIVE_REQUIRED"
            )
        return value

    async def reserve(self, lease: BulkLease) -> None:
        async with self.queue.publication(lease):
            facade = self.facade()
            workspace = await facade.catalog.get(
                lease.subject, lease.tenant_id, lease.destination.workspace_id
            )
            binding = await facade._workspace(
                lease.subject,
                lease.tenant_id,
                workspace,
                "canon" if lease.mode == "document" else "structured",
            )
            _, item, _ = await self.records.fenced(
                lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt
            )
            if item.native_workspace_id is not None and item.native_workspace_id != binding.native_id:
                raise ConflictException("Reserved native workspace changed", code="BULK_NATIVE_SCOPE_CHANGED")
            item.native_workspace_id = binding.native_id
            await self.records.flush()

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def workspace(self, lease: BulkLease) -> str:
        item = await self.records.receipt_item(lease.batch_id, lease.item_id)
        if (
            item is None
            or item.source_id != lease.source_id
            or item.asset_id != lease.asset_id
            or not item.native_workspace_id
        ):
            raise ConflictException("Native reservation is unavailable", code="BULK_NATIVE_SCOPE_CHANGED")
        return item.native_workspace_id

    async def inspect(self, lease: BulkLease) -> NativeObservation:
        return await self._inspect(lease, receipt_only=False)

    async def inspect_committed(self, lease: BulkLease) -> NativeObservation:
        return await self._inspect(lease, receipt_only=True)

    async def _inspect(self, lease: BulkLease, *, receipt_only: bool) -> NativeObservation:
        if lease.mode == "dataset":
            datasets = self.facade().domains._resolve(DatasetBulkNative)
            return await (datasets.inspect_committed(lease) if receipt_only else datasets.inspect(lease))
        if lease.mode != "document":
            raise ConflictException("Unsupported intake mode", code="BULK_MODE_UNAVAILABLE")
        from flycanon.core.services.sources.lineage.dtos import DocumentScope
        from flycanon.core.services.sources.lineage.ports import LineageQuery
        from flycanon.core.services.sources.lineage.service import DocumentLineage

        from koinon.knowledge.adapters import native_scope

        workspace = await self.workspace(lease)
        facade = self.facade()
        with native_scope("canon", lease.tenant_id, workspace, lease.subject):
            lineage = facade.domains._resolve(DocumentLineage)
            scope = DocumentScope(lease.tenant_id, workspace, lease.subject)
            async with lineage.repository.read() as unit:
                version = await unit.first(
                    LineageQuery(
                        "version",
                        scope,
                        equal={"operation_id": "upload:" + lease.source_id},
                        projection="intake_receipt",
                    )
                )
                if version is None:
                    return NativeObservation("absent")
                artifact = await unit.one(
                    LineageQuery(
                        "artifact",
                        scope,
                        source_id=version["source_id"],
                        equal={"id": version["artifact_id"]},
                        projection="intake_receipt",
                    )
                )
                if (
                    version["logical_key"] != lease.source_id
                    or artifact["sha256"] != lease.sha256
                    or artifact["bytes"] != lease.size_bytes
                ):
                    raise ConflictException(
                        "Native operation differs from reserved original", code="BULK_NATIVE_RECEIPT_CONFLICT"
                    )
                extraction = await unit.first(
                    LineageQuery(
                        "extraction",
                        scope,
                        source_id=version["source_id"],
                        equal={"version_id": version["id"], "purpose": "ingestion"},
                        projection="intake_receipt",
                    )
                )
                if extraction is None:
                    if receipt_only:
                        return NativeObservation("admitted")
                    from koinon.knowledge.bulk.failed_native import failed_native_proof

                    published = await unit.count(
                        LineageQuery(
                            "extraction",
                            scope,
                            source_id=version["source_id"],
                            equal={"version_id": version["id"]},
                        )
                    )
                    failure = await failed_native_proof(
                        unit, scope, version, lease, published=bool(published)
                    )
                    if failure is not None:
                        return NativeObservation("failed", failure=failure)
                    return NativeObservation("admitted")
                return NativeObservation(
                    "committed",
                    NativeCommit(
                        domain="canon",
                        native_workspace_id=workspace,
                        native_source_id=version["source_id"],
                        native_asset_id=version["source_id"],
                        sha256=artifact["sha256"],
                        size_bytes=artifact["bytes"],
                        source_version_id=version["id"],
                        extraction_id=extraction["id"],
                        n_chunks=extraction["n_chunks"],
                        object_key=artifact["object_key"],
                        source_attempt_id=(version.get("source_publication_json") or {}).get("attempt_id"),
                        source_publication_sha256=(version.get("source_publication_json") or {}).get(
                            "descriptor_sha256"
                        ),
                    ),
                )

    async def execute_file(self, lease: BulkLease, path) -> NativeCommit:
        if lease.mode == "dataset":
            # Dataset parsing is independently resource-fenced by its native reader.
            return await self.execute(lease, path.read_bytes())
        return await self.execute(lease, None, content_file=path)

    async def execute(self, lease: BulkLease, content: bytes | None, *, content_file=None) -> NativeCommit:
        if lease.mode == "dataset":
            return await self.facade().domains._resolve(DatasetBulkNative).execute(lease, content)
        if lease.mode != "document":
            raise ConflictException("Unsupported intake mode", code="BULK_MODE_UNAVAILABLE")
        facade = self.facade()
        workspace = await self.workspace(lease)
        source_publication = None
        writer = self.queue.source_writers.get() if self.queue.source_writers is not None else None
        admission = await writer.admission_for(lease) if writer is not None else None
        if writer is not None and admission is not None:
            from flycanon.core.services.sources.lineage.dtos import SourcePublicationBinding

            async with self.queue.publication(lease) as current:
                retained = await writer.freeze_publication(current, execution=lease)
            source_publication = SourcePublicationBinding(retained.attempt_id, retained.descriptor_sha256)

        async def processing():
            await self.queue.check(lease)

        active_publication = []

        @asynccontextmanager
        async def publication_guard():
            async with self.queue.publication(lease) as admission:
                if active_publication:
                    raise ConflictException("Publication cannot nest", code="SOURCE_PUBLICATION_DENIED")
                active_publication.append(admission)
                try:
                    yield
                finally:
                    active_publication.clear()

        async def publication():
            if not active_publication:
                raise ConflictException("Publication fence is unavailable", code="SOURCE_PUBLICATION_DENIED")
            await self.queue._check(lease, _source_admission=active_publication[0])

        await facade.domains.ingest_document(
            tenant_id=lease.tenant_id,
            workspace_id=workspace,
            catalog_workspace_id=lease.destination.workspace_id,
            actor=lease.subject,
            source_catalog_id=lease.source_id,
            filename=lease.filename,
            content=content,
            content_file=content_file,
            publication_guard=publication_guard,
            validate_processing=processing,
            validate_publication=publication,
            **({"_source_publication": source_publication} if source_publication is not None else {}),
        )
        result = await self.inspect(lease)
        if result.receipt is None:
            raise ConflictException(
                "Native success has no immutable commit receipt", code="BULK_NATIVE_RECEIPT_REQUIRED"
            )
        return result.receipt

    async def finalize_prepared(self, lease: BulkLease) -> NativeCommit:
        if lease.mode != "dataset":
            raise ConflictException(
                "Only complete dataset manifests can finalize", code="BULK_NATIVE_OUTCOME_UNRESOLVED"
            )
        return await self.facade().domains._resolve(DatasetBulkNative).finalize_prepared(lease)

    async def acknowledge(self, lease: BulkLease, receipt: NativeCommit) -> None:
        writer = self.queue.source_writers.get() if self.queue.source_writers is not None else None
        admission = await writer.admission_for(lease) if writer is not None else None
        if writer is not None and admission is not None:
            if await writer.replay_publication(admission, lease, receipt):
                return
            observed = await self.inspect_committed(lease)
            if observed.status != "committed" or observed.receipt != receipt:
                raise ConflictException(
                    "Exact committed source receipt is required", code="BULK_NATIVE_RECEIPT_CONFLICT"
                )
            async with self.queue.publication(lease) as admission:
                if admission is None:
                    raise ConflictException("Source admission disappeared", code="SOURCE_PUBLICATION_DENIED")
                entries, operations = await writer.publication_plan(admission, lease, receipt)
                facade = self.facade()
                by_id = {entry.id: entry for entry in entries}
                details = {
                    "source_version_id": receipt.source_version_id,
                    "extraction_id": receipt.extraction_id,
                    "n_chunks": receipt.n_chunks,
                    "object_store_key": receipt.object_key,
                }
                async with writer.open(admission, operations) as permit:
                    for identifier, native in (
                        (lease.source_id, receipt.native_source_id),
                        (lease.asset_id, receipt.native_asset_id),
                    ):
                        await facade._bind(
                            lease.subject,
                            lease.tenant_id,
                            by_id[identifier],
                            receipt.domain,
                            native,
                            receipt.native_workspace_id,
                            details,
                        )
                    for table in receipt.tables:
                        await facade._bind(
                            lease.subject,
                            lease.tenant_id,
                            by_id[table.catalog_table_id],
                            "structured",
                            table.table_id,
                            receipt.native_workspace_id,
                            {**asdict(table), "file_id": receipt.native_file_id},
                        )
                    if receipt.file_version_id:
                        await facade._bind(
                            lease.subject,
                            lease.tenant_id,
                            by_id[receipt.file_version_id],
                            "structured",
                            receipt.native_file_id,
                            receipt.native_workspace_id,
                            {
                                "dataset_id": receipt.native_asset_id,
                                "table_ids": [t.catalog_table_id for t in receipt.tables],
                            },
                        )
                    for entry in entries:
                        await facade.catalog.update(
                            lease.subject,
                            lease.tenant_id,
                            entry.id,
                            {"status": "ready"},
                            _source_write=permit,
                            _source_parent_id=entry.parent_id,
                        )
                async with writer.completion(admission, lease, receipt):
                    job, item, batch = await self.records.fenced(
                        lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt
                    )
                    await self._record_success(lease, receipt, job, item, batch)
            return
        await self._acknowledge(lease, receipt)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def _acknowledge(self, lease: BulkLease, receipt: NativeCommit) -> None:
        await self.queue._check(lease)
        await self.acknowledge_committed(lease, receipt)

    async def settle_source_receipt(self, lease: BulkLease, receipt: NativeCommit) -> None:
        await self.queue.reconcile_source(lease)
        observed = await self.inspect_committed(lease)
        if observed.status != "committed" or observed.receipt != receipt:
            raise ConflictException(
                "Exact committed source receipt is required", code="BULK_NATIVE_RECEIPT_CONFLICT"
            )
        await self._settle_source_receipt(lease, receipt)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def _settle_source_receipt(self, lease: BulkLease, receipt: NativeCommit) -> None:
        job, item, batch = await self.queue._reconcile_source(lease)
        encoded = json.loads(json.dumps(asdict(receipt)))
        if (
            receipt.sha256 != item.sha256
            or receipt.size_bytes != item.size_bytes
            or receipt.native_workspace_id != item.native_workspace_id
            or receipt.domain != ("canon" if item.mode == "document" else "structured")
            or not await self.records.receipt_matches(
                item.id,
                encoded,
                allow_missing=item.status != "succeeded",
            )
        ):
            raise ConflictException("Source receipt differs", code="BULK_NATIVE_RECEIPT_CONFLICT")
        if item.status == "succeeded":
            return
        guard = self.queue.source_fences.get() if self.queue.source_fences is not None else None
        if guard is None:
            raise ConflictException("Source receipt fence is required", code="SOURCE_PUBLICATION_DENIED")
        await guard.settle(lease, receipt)
        await self.records.settle_receipt(job.id, item.id, batch.id, encoded)
        await self.queue.authority.catalog._audit(
            lease.subject,
            lease.tenant_id,
            "knowledge.source.receipt_recorded",
            item.id,
            {"source_id": item.source_id, "asset_id": item.asset_id},
        )
        await self.records.flush()

    @transactional
    async def acknowledge_committed(self, lease: BulkLease, receipt: NativeCommit) -> None:
        from koinon.knowledge.bulk.authority import token_identity

        await self.queue.authority.destination(lease.subject, lease.tenant_id, lease.destination, write=True)
        await self.queue.authority.item(
            lease.subject, lease.tenant_id, lease.source_id, lease.asset_id, lease.destination, lease.sha256
        )
        candidate = await self.records.item(lease.batch_id, lease.item_id)
        if candidate is not None and candidate.mode == "dataset":
            await self.queue.authority.dataset(lease.subject, lease.tenant_id, candidate, lease.destination)
        await self.queue.source_check(lease, reconcile=True)
        batch = await self.records.scoped(lease.tenant_id, lease.subject, lease.batch_id, lock=True)
        item = await self.records.item(lease.batch_id, lease.item_id, lock=True)
        job = await self.records.job(item.job_id) if item and item.job_id else None
        if (
            batch is None
            or item is None
            or job is None
            or batch.token_id != token_identity()
            or item.source_id != lease.source_id
            or item.asset_id != lease.asset_id
        ):
            raise ConflictException("Reserved primary operation differs", code="BULK_NATIVE_RECEIPT_CONFLICT")
        if item.status == "succeeded":
            if item.receipt_json != json.loads(json.dumps(asdict(receipt))):
                raise ConflictException("Committed receipt is immutable", code="BULK_NATIVE_RECEIPT_CONFLICT")
            return
        if item.connection_json != await self.records.connection(
            batch.tenant_id, batch.workspace_id, item.mode
        ):
            raise ConflictException("Admitted embedding connection changed", code="BULK_CONNECTION_CHANGED")
        if not await self.records.workspace_matches(
            batch.tenant_id,
            batch.workspace_id,
            "canon" if item.mode == "document" else "structured",
            item.native_workspace_id or "",
        ):
            raise ConflictException("Reserved native workspace changed", code="BULK_NATIVE_SCOPE_CHANGED")
        observed = await self.inspect_committed(lease)
        if observed.status != "committed" or observed.receipt != receipt:
            raise ConflictException(
                "Only an exact existing native commit can be acknowledged",
                code="BULK_NATIVE_RECEIPT_CONFLICT",
            )
        if (
            receipt.sha256 != item.sha256
            or receipt.size_bytes != item.size_bytes
            or receipt.native_workspace_id != item.native_workspace_id
            or receipt.domain != ("canon" if item.mode == "document" else "structured")
        ):
            raise ConflictException(
                "Native receipt differs from immutable item", code="BULK_NATIVE_RECEIPT_CONFLICT"
            )
        facade = self.facade()
        source = await facade.catalog.get(lease.subject, lease.tenant_id, item.source_id)
        asset = await facade.catalog.get(lease.subject, lease.tenant_id, item.asset_id)
        if (
            source.kind != "source"
            or source.parent_id != batch.parent_id
            or asset.parent_id != source.id
            or asset.kind != item.mode
            or source.metadata_json.get("sha256") != item.sha256
        ):
            raise ConflictException("Reserved catalog destination changed", code="BULK_DESTINATION_CHANGED")
        details = {
            "source_version_id": receipt.source_version_id,
            "extraction_id": receipt.extraction_id,
            "n_chunks": receipt.n_chunks,
            "object_store_key": receipt.object_key,
        }
        await facade._bind(
            lease.subject,
            lease.tenant_id,
            source,
            receipt.domain,
            receipt.native_source_id,
            receipt.native_workspace_id,
            details,
        )
        await facade._bind(
            lease.subject,
            lease.tenant_id,
            asset,
            receipt.domain,
            receipt.native_asset_id,
            receipt.native_workspace_id,
            details,
        )
        if item.mode == "dataset":
            reservation = DatasetReservation.stored(item.reservation_json)
            tables = await self.records.table_reservations(item.id)
            if (
                receipt.file_version_id != reservation.catalog_file_version_id
                or receipt.native_file_id != str(reservation.native_file_id)
                or receipt.native_asset_id != str(reservation.native_dataset_id)
                or len(tables) != len(receipt.tables)
                or not tables
                or any(
                    (row.catalog_table_id, row.table_id, row.snapshot_id)
                    != (table.catalog_table_id, table.table_id, table.snapshot_id)
                    for row, table in zip(tables, receipt.tables, strict=True)
                )
            ):
                raise ConflictException(
                    "Dataset receipt differs from reserved tables", code="BULK_NATIVE_RECEIPT_CONFLICT"
                )
            for table in receipt.tables:
                node = await facade.catalog.get(lease.subject, lease.tenant_id, table.catalog_table_id)
                await facade._bind(
                    lease.subject,
                    lease.tenant_id,
                    node,
                    "structured",
                    table.table_id,
                    receipt.native_workspace_id,
                    {**asdict(table), "file_id": receipt.native_file_id},
                )
                await facade.catalog.update(lease.subject, lease.tenant_id, node.id, {"status": "ready"})
            version = await facade.catalog.get(
                lease.subject, lease.tenant_id, reservation.catalog_file_version_id
            )
            await facade._bind(
                lease.subject,
                lease.tenant_id,
                version,
                "structured",
                receipt.native_file_id,
                receipt.native_workspace_id,
                {
                    "dataset_id": receipt.native_asset_id,
                    "table_ids": [t.catalog_table_id for t in receipt.tables],
                },
            )
            await facade.catalog.update(lease.subject, lease.tenant_id, version.id, {"status": "ready"})
        await facade.catalog.update(lease.subject, lease.tenant_id, source.id, {"status": "ready"})
        await facade.catalog.update(lease.subject, lease.tenant_id, asset.id, {"status": "ready"})
        await self._record_success(lease, receipt, job, item, batch)

    async def _record_success(self, lease, receipt, job, item, batch):
        item.receipt_json = json.loads(json.dumps(asdict(receipt)))
        item.native_id = receipt.native_asset_id
        item.status = "succeeded"
        item.error_code = None
        job.status = "succeeded"
        job.progress = 100
        job.result = {
            "batch_id": batch.id,
            "item_id": item.id,
            "source_id": item.source_id,
            "asset_id": item.asset_id,
        }
        job.worker_id = None
        job.lease_until = None
        batch.revision += 1
        source_fence = self.queue.source_fences.get() if self.queue.source_fences is not None else None
        if source_fence is not None:
            await source_fence.committed(lease, receipt)
        await self.records.flush()
