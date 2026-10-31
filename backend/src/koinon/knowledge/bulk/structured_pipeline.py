# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Compose existing native stages; publish a complete prepared dataset without replay."""

import hashlib
import json
from contextlib import suppress
from pathlib import Path
from uuid import UUID, uuid5

from flyquery.core.eda.ingest_publisher import IngestPublisher
from flyquery.core.services.ingestion import lineage
from flyquery.core.services.ingestion.reader import ProposedTable
from flyquery.core.services.ingestion.resources import resource_scope
from flyquery.core.services.ingestion.stages.embed import run_embed
from flyquery.core.services.ingestion.stages.parse import ParsedTable, _sanitise_name, run_parse
from flyquery.core.services.ingestion.stages.profile import run_profile
from flyquery.core.services.ingestion.stages.publish import run_publish
from flyquery.core.services.ingestion.stages.receive import ReceiveResult, run_receive
from flyquery.core.services.ingestion.stages.reconcile import run_reconcile
from flyquery.core.services.ingestion.stages.sample import run_sample
from flyquery.core.services.storage.object_store import ObjectStore
from flyquery.core.services.workspaces.workspace_service import WorkspaceService
from pyfly.container import Provider, service
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.knowledge.bulk.queue import BulkLease, BulkQueue
from koinon.knowledge.bulk.structured_dtos import (
    PreparedStructuredTable,
    StructuredOperationIdentity,
    StructuredOperationState,
    StructuredTablePlan,
)
from koinon.knowledge.bulk.structured_repository import StructuredBulkRepository


@service(name="knowledge.bulk.structured_pipeline")
class StructuredBulkPipeline:
    def __init__(
        self,
        operations: StructuredBulkRepository,
        queue: BulkQueue,
        stores: Provider[ObjectStore | None],
        workspaces: Provider[WorkspaceService | None],
        publishers: Provider[IngestPublisher | None],
    ):
        self.operations, self.queue, self.stores, self.workspaces, self.publishers = (
            operations,
            queue,
            stores,
            workspaces,
            publishers,
        )

    @staticmethod
    def _identity(lease: BulkLease, identity: StructuredOperationIdentity) -> None:
        if (
            identity.operation_id != UUID(lease.item_id)
            or identity.actor != lease.subject
            or identity.tenant_id != lease.tenant_id
            or identity.catalog_source_id != lease.source_id
            or identity.catalog_dataset_id != lease.asset_id
            or identity.filename != lease.filename
            or identity.sha256 != lease.sha256
            or identity.size_bytes != lease.size_bytes
        ):
            raise ConflictException(
                "Dataset operation differs from its current lease", code="BULK_NATIVE_RECEIPT_CONFLICT"
            )

    async def prepare(
        self, lease: BulkLease, identity: StructuredOperationIdentity, content: bytes
    ) -> StructuredOperationState:
        self._identity(lease, identity)
        if len(content) != identity.size_bytes or hashlib.sha256(content).hexdigest() != identity.sha256:
            raise ConflictException("Original bytes differ from admission", code="BULK_ORIGINAL_INTEGRITY")
        await self.queue.check(lease)
        settings = self.operations.configuration()
        with resource_scope(settings):
            native = self.operations.native()
            store, workspaces = self.stores.get(), self.workspaces.get()
            if store is None or workspaces is None:
                raise ServiceUnavailableException(
                    "Native dataset resources are unavailable", code="BULK_NATIVE_REQUIRED"
                )
            async with self.queue.publication(lease), self.operations.write() as unit:
                if await unit.get(identity) is not None:
                    raise ConflictException(
                        "Existing native work requires receipt reconciliation",
                        code="BULK_NATIVE_OUTCOME_UNRESOLVED",
                    )
                await unit.admit(identity)
            plans: tuple[StructuredTablePlan, ...] = ()
            received: ReceiveResult | None = None
            parsed: list[ParsedTable] = []

            async def reserve_tables(proposed: tuple[ProposedTable, ...]) -> tuple[UUID, ...]:
                nonlocal plans
                if not 1 <= len(proposed) <= 16:
                    raise ConflictException(
                        "A dataset requires a bounded complete table set", code="BULK_TABLE_LIMIT"
                    )
                plans = tuple(
                    StructuredTablePlan(
                        ordinal=i,
                        table_id=uuid5(identity.operation_id, f"table:{i}"),
                        snapshot_id=uuid5(identity.operation_id, f"snapshot:{i}"),
                        name=_sanitise_name(
                            Path(identity.filename).stem if len(proposed) == 1 else value.name
                        ),
                    )
                    for i, value in enumerate(proposed)
                )
                plans = await self.queue.reserve_tables(lease, plans)
                async with self.queue.publication(lease), self.operations.write() as unit:
                    await unit.plan(identity, plans)
                return tuple(plan.table_id for plan in plans)

            try:
                async with self.queue.publication(lease):
                    workspace = await workspaces.get(identity.workspace_id)
                    if workspace is None or workspace["tenant_id"] != identity.tenant_id:
                        raise ConflictException("Native workspace differs", code="BULK_NATIVE_SCOPE_CHANGED")
                    received = await run_receive(
                        tenant_id=identity.tenant_id,
                        workspace_id=identity.workspace_id,
                        dataset_id=identity.dataset_id,
                        filename=identity.filename,
                        file_bytes=content,
                        actor=identity.actor,
                        object_store=store,
                        session_factory=native.sessionmaker,
                        settings=settings,
                        workspace_storage_used_bytes=workspace["storage_used_bytes"],
                        file_id=identity.file_id,
                    )
                    if (
                        received.file_id != identity.file_id
                        or received.size_bytes != identity.size_bytes
                        or received.content_hash_sha256 != identity.sha256
                    ):
                        raise ConflictException(
                            "Received original differs from admission", code="BULK_ORIGINAL_INTEGRITY"
                        )
                    await workspaces.track_storage(identity.workspace_id, received.size_bytes)
                await self.queue.check(lease)
                parsed = await run_parse(
                    tenant_id=identity.tenant_id,
                    workspace_id=identity.workspace_id,
                    dataset_id=identity.dataset_id,
                    file_id=identity.file_id,
                    local_temp_path=received.local_temp_path,
                    file_format=received.file_format,
                    compression=received.compression,
                    object_store=store,
                    session_factory=native.sessionmaker,
                    settings=settings,
                    dataset_name="bulk_" + str(identity.operation_id),
                    workspace_locale=settings.default_locale,
                    original_filename=identity.filename,
                    append_only=True,
                    max_tables=16,
                    extract_only=True,
                    reserve_tables=reserve_tables,
                )
                if len(parsed) != len(plans) or not plans:
                    raise ConflictException(
                        "Not every reserved table was materialized", code="BULK_NATIVE_OUTCOME_UNRESOLVED"
                    )
                prepared = []
                for plan, table in zip(plans, parsed, strict=True):
                    await self.queue.check(lease)
                    if (
                        table.table_id != plan.table_id
                        or table.name != plan.name
                        or not table.local_parquet_path
                    ):
                        raise ConflictException(
                            "Materialized table identity differs", code="BULK_NATIVE_RECEIPT_CONFLICT"
                        )
                    receipt = table.lineage_receipt or {}
                    run_id = receipt.get("run_id")
                    if not run_id:
                        raise ConflictException(
                            "Native extraction has no immutable lineage", code="BULK_NATIVE_RECEIPT_REQUIRED"
                        )
                    reconciled = await run_reconcile(
                        tenant_id=identity.tenant_id,
                        workspace_id=identity.workspace_id,
                        dataset_id=identity.dataset_id,
                        parsed=table,
                        actor=identity.actor,
                        triggered_by="USER",
                        session_factory=native.sessionmaker,
                        settings=settings,
                        snapshot_id=plan.snapshot_id,
                    )
                    await self.queue.check(lease)
                    async with lineage.stage(run_id, "sample"):
                        await run_sample(
                            tenant_id=identity.tenant_id,
                            snapshot_id=plan.snapshot_id,
                            parquet_key=table.local_parquet_path,
                            session_factory=native.sessionmaker,
                            settings=settings,
                        )
                    await self.queue.check(lease)
                    async with lineage.stage(run_id, "profile"):
                        await run_profile(
                            tenant_id=identity.tenant_id,
                            snapshot_id=plan.snapshot_id,
                            parquet_key=table.local_parquet_path,
                            n_rows_actual=reconciled.n_rows_actual,
                            session_factory=native.sessionmaker,
                            settings=settings,
                        )
                    await self.queue.check(lease)
                    async with lineage.stage(run_id, "embed"):
                        embedded = await run_embed(
                            tenant_id=identity.tenant_id,
                            snapshot_id=plan.snapshot_id,
                            session_factory=native.sessionmaker,
                            settings=settings,
                        )
                    if (
                        embedded["objects_processed"] < 1
                        or embedded["embeddings_written"] != embedded["objects_processed"]
                    ):
                        raise ConflictException(
                            "Every schema object requires its admitted embedding",
                            code="BULK_EMBEDDING_INCOMPLETE",
                        )
                    await self.queue.check(lease)
                    with Path(table.local_parquet_path).open("rb") as stream:
                        parquet_digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    if receipt.get("parquet_sha256") != parquet_digest:
                        raise ConflictException(
                            "Prepared Parquet bytes changed", code="BULK_ORIGINAL_INTEGRITY"
                        )
                    schema_digest = hashlib.sha256(
                        json.dumps(sorted((c.name, c.data_type) for c in table.result.columns)).encode()
                    ).hexdigest()
                    prepared.append(
                        PreparedStructuredTable(
                            **plan.model_dump(),
                            lineage_run_id=UUID(run_id),
                            n_columns=reconciled.n_columns,
                            n_rows_actual=reconciled.n_rows_actual,
                            parquet_key=table.parquet_key,
                            parquet_sha256=parquet_digest,
                            parquet_byte_size=Path(table.local_parquet_path).stat().st_size,
                            schema_sha256=schema_digest,
                        )
                    )
                async with self.queue.publication(lease), self.operations.write() as unit:
                    return await unit.prepared(identity, tuple(prepared))
            finally:
                for table in parsed:
                    if table.local_parquet_path:
                        with suppress(OSError):
                            Path(table.local_parquet_path).unlink(missing_ok=True)
                if received is not None:
                    with suppress(OSError):
                        Path(received.local_temp_path).unlink(missing_ok=True)

    async def finalize(
        self, lease: BulkLease, identity: StructuredOperationIdentity
    ) -> StructuredOperationState:
        self._identity(lease, identity)
        await self.queue.check(lease)
        native = self.operations.native()
        publisher = self.publishers.get()
        if publisher is None:
            raise ServiceUnavailableException(
                "Native publication is unavailable", code="BULK_NATIVE_REQUIRED"
            )
        async with self.queue.publication(lease), self.operations.write() as unit:
            state = await unit.publication(identity)
            if state.status == "committed":
                return state
            for table in state.prepared:
                async with lineage.stage(str(table.lineage_run_id), "publish", completion=False):
                    await run_publish(
                        tenant_id=identity.tenant_id,
                        workspace_id=identity.workspace_id,
                        dataset_id=identity.dataset_id,
                        table_id=table.table_id,
                        snapshot_id=table.snapshot_id,
                        n_columns=table.n_columns,
                        n_rows_actual=table.n_rows_actual,
                        publisher=publisher,
                        session_factory=native.sessionmaker,
                        emit_event=False,
                    )
            await self.queue._check(lease)
            return await unit.commit(identity)
