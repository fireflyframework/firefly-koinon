# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Canonical intake ports reuse native lineage receipts instead of replaying completed work."""

import json
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
        item = await self.records.item(lease.batch_id, lease.item_id)
        if (
            item is None
            or item.source_id != lease.source_id
            or item.asset_id != lease.asset_id
            or not item.native_workspace_id
        ):
            raise ConflictException("Native reservation is unavailable", code="BULK_NATIVE_SCOPE_CHANGED")
        return item.native_workspace_id

    async def inspect(self, lease: BulkLease) -> NativeObservation:
        if lease.mode == "dataset":
            return await self.facade().domains._resolve(DatasetBulkNative).inspect(lease)
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
                    LineageQuery("version", scope, equal={"operation_id": "upload:" + lease.source_id})
                )
                if version is None:
                    return NativeObservation("absent")
                artifact = await unit.one(
                    LineageQuery(
                        "artifact",
                        scope,
                        source_id=version["source_id"],
                        equal={"id": version["artifact_id"]},
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
                    )
                )
                if extraction is None:
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
                        n_chunks=extraction["projection"]["n_chunks"],
                        object_key=artifact["object_key"],
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

        async def processing():
            await self.queue.check(lease)

        async def publication():
            await self.queue._check(lease)

        await facade.domains.ingest_document(
            tenant_id=lease.tenant_id,
            workspace_id=workspace,
            catalog_workspace_id=lease.destination.workspace_id,
            actor=lease.subject,
            source_catalog_id=lease.source_id,
            filename=lease.filename,
            content=content,
            content_file=content_file,
            publication_guard=lambda: self.queue.publication(lease),
            validate_processing=processing,
            validate_publication=publication,
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

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def acknowledge(self, lease: BulkLease, receipt: NativeCommit) -> None:
        await self.queue._check(lease)
        await self.acknowledge_committed(lease, receipt)

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
        observed = await self.inspect(lease)
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
        await self.records.flush()
