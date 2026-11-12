# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Compose existing native stages; publish a complete prepared dataset without replay."""

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager, suppress
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
from flyquery.core.services.ingestion.stages.receive import ReceiveResult, original_object_key, run_receive
from flyquery.core.services.ingestion.stages.reconcile import publish_reconcile_changes, run_reconcile
from flyquery.core.services.ingestion.stages.sample import run_sample
from flyquery.core.services.storage.object_store import ObjectStore
from flyquery.core.services.workspaces.workspace_service import WorkspaceService
from pydantic import ValidationError
from pyfly.container import Provider, service
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.integrations.content_sources.sync_runs import SourceReplacementExecution
from koinon.knowledge.bulk.queue import BulkLease, BulkQueue
from koinon.knowledge.bulk.structured_dtos import (
    DatasetReplacementBaseline,
    PreparedStructuredTable,
    ReplacementMemberPlan,
    SourceReplacementDiscovery,
    StructuredOperationIdentity,
    StructuredOperationState,
    StructuredTablePlan,
)
from koinon.knowledge.bulk.structured_replacement import PARSER_FINGERPRINT, discover_members
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

    @staticmethod
    def _source_authority(admission, producer, lease, identity) -> None:
        if admission is None and producer is None and not isinstance(lease, SourceReplacementExecution):
            return
        if (
            admission is None
            or producer is None
            or producer.admission != admission
            or producer.execution != lease
            or producer.operation != identity
        ):
            raise ConflictException(
                "The dataset requires its exact source producer", code="SOURCE_PUBLICATION_DENIED"
            )
        producer.check()

    @asynccontextmanager
    async def _publication(self, execution, producer):
        gate = (
            producer.publication()
            if isinstance(execution, SourceReplacementExecution)
            else self.queue.publication(execution)
        )
        async with gate as admission:
            yield admission

    async def _check(self, execution, producer):
        if isinstance(execution, SourceReplacementExecution):
            async with self._publication(execution, producer) as admission:
                self._source_authority(admission, producer, execution, producer.operation)
        else:
            await self.queue.check(execution)

    @staticmethod
    def _replacement_identity(execution, identity, admission, producer):
        StructuredBulkPipeline._source_authority(admission, producer, execution, identity)
        if (
            type(execution) is not SourceReplacementExecution
            or str(identity.operation_id) != execution.content_operation_id
            or identity.tenant_id != execution.run_lease.tenant_id
            or identity.actor != execution.run_lease.owner
            or producer.attempt_id != execution.attempt_id
        ):
            raise ConflictException(
                "The dataset requires its exact source producer", code="SOURCE_PUBLICATION_DENIED"
            )

    async def prepare_replacement(
        self,
        execution: SourceReplacementExecution,
        identity: StructuredOperationIdentity,
        content: bytes,
        *,
        source_admission,
        source_producer,
        baseline: DatasetReplacementBaseline,
        baseline_sha256: str,
        members: tuple[ReplacementMemberPlan, ...],
        discovery_evidence: SourceReplacementDiscovery,
    ) -> StructuredOperationState:
        self._replacement_identity(execution, identity, source_admission, source_producer)
        with lineage.observe(source_producer):
            return await self._prepare(
                execution,
                identity,
                content,
                _source_producer=source_producer,
                replacement=(baseline, baseline_sha256, members, discovery_evidence),
            )

    async def prepare(
        self,
        lease: BulkLease,
        identity: StructuredOperationIdentity,
        content: bytes,
        *,
        _source_producer=None,
    ) -> StructuredOperationState:
        self._identity(lease, identity)
        return await self._prepare(lease, identity, content, _source_producer=_source_producer)

    async def _prepare(self, lease, identity, content, *, _source_producer=None, replacement=None):
        retained_admission = None
        if replacement is not None and _source_producer is None:
            raise ConflictException(
                "The dataset requires its exact source producer", code="SOURCE_PUBLICATION_DENIED"
            )
        if replacement is not None:
            assert _source_producer is not None
            baseline, baseline_sha256, members, evidence = replacement
            async with (
                self._publication(lease, _source_producer) as admission,
                self.operations.write() as unit,
            ):
                self._source_authority(admission, _source_producer, lease, identity)
                existing = await unit.get(identity)
                if existing is not None:
                    if (
                        existing.operation_kind != "replace"
                        or existing.baseline != baseline
                        or existing.baseline_sha256 != baseline_sha256
                        or existing.replacement_plan != members
                        or existing.source_attempt_id != _source_producer.attempt_id
                    ):
                        raise ConflictException(
                            "Replacement recovery identity differs", code="BULK_NATIVE_RECEIPT_CONFLICT"
                        )
                    await _source_producer.plans(unit._session)
                    if existing.status in {"prepared", "committed"}:
                        return existing
                    retained_admission = existing
        if len(content) != identity.size_bytes or hashlib.sha256(content).hexdigest() != identity.sha256:
            raise ConflictException("Original bytes differ from admission", code="BULK_ORIGINAL_INTEGRITY")
        if replacement is not None:
            try:
                evidence = SourceReplacementDiscovery.model_validate(evidence.model_dump())
            except (AttributeError, ValidationError):
                raise ConflictException(
                    "Parser discovery differs from its frozen source evidence",
                    code="BULK_NATIVE_RECEIPT_CONFLICT",
                ) from None
            if evidence.content_sha256 != identity.sha256:
                raise ConflictException(
                    "Discovery bytes differ from admission", code="BULK_ORIGINAL_INTEGRITY"
                )
        await self._check(lease, _source_producer)
        settings = self.operations.configuration()
        with resource_scope(settings):
            native = self.operations.native()
            store, workspaces = self.stores.get(), self.workspaces.get()
            if store is None or workspaces is None:
                raise ServiceUnavailableException(
                    "Native dataset resources are unavailable", code="BULK_NATIVE_REQUIRED"
                )
            async with (
                self._publication(lease, _source_producer) as admission,
                self.operations.write() as unit,
            ):
                self._source_authority(admission, _source_producer, lease, identity)
                current = await unit.get(identity)
                if retained_admission is not None:
                    if current != retained_admission:
                        raise ConflictException(
                            "Replacement recovery identity differs", code="BULK_NATIVE_RECEIPT_CONFLICT"
                        )
                elif current is not None:
                    raise ConflictException(
                        "Existing native work requires receipt reconciliation",
                        code="BULK_NATIVE_OUTCOME_UNRESOLVED",
                    )
                if replacement is not None and retained_admission is None:
                    assert _source_producer is not None
                    await unit.admit_replacement(
                        identity,
                        source_attempt_id=_source_producer.attempt_id,
                        baseline=baseline,
                        baseline_sha256=baseline_sha256,
                    )
                    planned = await unit.plan_replacement(identity, members)
                    binding = await _source_producer.freeze(admission, planned.replacement_plan)
                    await unit.bind_publication(identity, binding)
                elif replacement is None and _source_producer is None:
                    await unit.admit(identity)
                elif replacement is None and _source_producer is not None:
                    await unit.admit(identity, source_attempt_id=_source_producer.attempt_id)
            plans: tuple[StructuredTablePlan, ...] = ()
            received: ReceiveResult | None = None
            parsed: list[ParsedTable] = []

            async def reserve_tables(proposed: tuple[ProposedTable, ...]) -> tuple[UUID, ...]:
                nonlocal plans
                if not 1 <= len(proposed) <= 16:
                    raise ConflictException(
                        "A dataset requires a bounded complete table set", code="BULK_TABLE_LIMIT"
                    )
                if received is None:
                    raise ConflictException(
                        "Original file has not been received", code="BULK_ORIGINAL_INTEGRITY"
                    )
                discovered = discover_members(received.file_format, proposed)
                if replacement is not None:
                    actual = SourceReplacementDiscovery.capture(
                        filename=identity.filename,
                        file_format=received.file_format,
                        compression=received.compression,
                        content_sha256=received.content_hash_sha256,
                        proposed=proposed,
                    )
                    live = tuple(member for member in members if member.action != "remove")
                    if actual != evidence or tuple(member.member_key for member in live) != tuple(
                        value.locator for value in discovered
                    ):
                        raise ConflictException(
                            "Parser discovery differs from its frozen source evidence",
                            code="BULK_NATIVE_RECEIPT_CONFLICT",
                        )
                    plans = tuple(
                        StructuredTablePlan(
                            **{field: getattr(member, field) for field in StructuredTablePlan.model_fields}
                        )
                        for member in live
                    )
                    return tuple(plan.table_id for plan in plans)
                plans = tuple(
                    StructuredTablePlan(
                        ordinal=i,
                        table_id=uuid5(identity.operation_id, f"table:{i}"),
                        snapshot_id=uuid5(identity.operation_id, f"snapshot:{i}"),
                        name=_sanitise_name(
                            Path(identity.filename).stem if len(proposed) == 1 else value.name
                        ),
                        member_key=discovered[i].locator,
                        parser_fingerprint=PARSER_FINGERPRINT,
                    )
                    for i, value in enumerate(proposed)
                )
                plans = await self.queue.reserve_tables(lease, plans)
                async with self._publication(lease, _source_producer) as admission:
                    async with self.operations.write() as unit:
                        await unit.plan(identity, plans)
                    if _source_producer is not None:
                        binding = await _source_producer.freeze(admission, plans)
                        async with self.operations.write() as unit:
                            await unit.bind_publication(identity, binding)
                return tuple(plan.table_id for plan in plans)

            try:
                async with self._publication(lease, _source_producer):
                    if retained_admission is not None:
                        key = original_object_key(
                            identity.tenant_id, identity.workspace_id, identity.dataset_id,
                            identity.file_id, identity.filename, evidence.file_format, evidence.compression,
                        )
                        async with self.operations.write() as unit:
                            absence = await unit.replacement_absence(retained_admission, key)
                        if absence is None:
                            return retained_admission
                        try:
                            async with asyncio.timeout(settings.object_store_request_timeout_seconds):
                                await store.head(absence.object_key)
                        except FileNotFoundError:
                            # The port distinguishes definite absence from permission/network failures.
                            pass
                        except Exception:
                            return retained_admission
                        else:
                            return retained_admission
                        async with self.operations.write() as unit:
                            if await unit.replacement_absence(retained_admission, key) != absence:
                                return retained_admission
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
                await self._check(lease, _source_producer)
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
                    _defer_table_bindings=_source_producer is not None,
                )
                if len(parsed) != len(plans) or not plans:
                    raise ConflictException(
                        "Not every reserved table was materialized", code="BULK_NATIVE_OUTCOME_UNRESOLVED"
                    )
                prepared = []
                for plan, table in zip(plans, parsed, strict=True):
                    await self._check(lease, _source_producer)
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
                    if _source_producer is not None:
                        async with (
                            self._publication(lease, _source_producer),
                            self.operations.write() as unit,
                        ):
                            await unit.materialize_table(identity, plan, table)
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
                        **(
                            {"guard": _source_producer, "defer_live_changes": True}
                            if _source_producer is not None
                            else {}
                        ),
                    )
                    await self._check(lease, _source_producer)
                    async with lineage.stage(run_id, "sample"):
                        await run_sample(
                            tenant_id=identity.tenant_id,
                            snapshot_id=plan.snapshot_id,
                            parquet_key=table.local_parquet_path,
                            session_factory=native.sessionmaker,
                            settings=settings,
                            **({"guard": _source_producer} if _source_producer is not None else {}),
                        )
                    await self._check(lease, _source_producer)
                    async with lineage.stage(run_id, "profile"):
                        await run_profile(
                            tenant_id=identity.tenant_id,
                            snapshot_id=plan.snapshot_id,
                            parquet_key=table.local_parquet_path,
                            n_rows_actual=reconciled.n_rows_actual,
                            session_factory=native.sessionmaker,
                            settings=settings,
                            **({"guard": _source_producer} if _source_producer is not None else {}),
                        )
                    await self._check(lease, _source_producer)
                    async with lineage.stage(run_id, "embed"):
                        embedded = await run_embed(
                            tenant_id=identity.tenant_id,
                            snapshot_id=plan.snapshot_id,
                            session_factory=native.sessionmaker,
                            settings=settings,
                            **({"guard": _source_producer} if _source_producer is not None else {}),
                        )
                    if (
                        embedded["objects_processed"] < 1
                        or embedded["embeddings_written"] != embedded["objects_processed"]
                    ):
                        raise ConflictException(
                            "Every schema object requires its admitted embedding",
                            code="BULK_EMBEDDING_INCOMPLETE",
                        )
                    await self._check(lease, _source_producer)
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
                            qualified_name=table.qualified_name,
                            sheet_or_json_path=table.sheet_or_json_path,
                            reconcile_changes=reconciled.pending_changes
                            if _source_producer is not None
                            else None,
                        )
                    )
                async with self._publication(lease, _source_producer), self.operations.write() as unit:
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
        self, lease: BulkLease, identity: StructuredOperationIdentity, *, _source_producer=None
    ) -> StructuredOperationState:
        self._identity(lease, identity)
        return await self._finalize(lease, identity, _source_producer=_source_producer)

    async def finalize_replacement(
        self,
        execution: SourceReplacementExecution,
        identity: StructuredOperationIdentity,
        *,
        source_admission,
        source_producer,
    ) -> StructuredOperationState:
        self._replacement_identity(execution, identity, source_admission, source_producer)
        with lineage.observe(source_producer):
            return await self._finalize(execution, identity, _source_producer=source_producer)

    async def _finalize(self, lease, identity, *, _source_producer=None):
        if isinstance(lease, SourceReplacementExecution) and _source_producer is None:
            raise ConflictException(
                "The dataset requires its exact source producer", code="SOURCE_PUBLICATION_DENIED"
            )
        await self._check(lease, _source_producer)
        native = self.operations.native()
        publisher = self.publishers.get()
        if publisher is None:
            raise ServiceUnavailableException(
                "Native publication is unavailable", code="BULK_NATIVE_REQUIRED"
            )
        async with self._publication(lease, _source_producer) as admission, self.operations.write() as unit:
            self._source_authority(admission, _source_producer, lease, identity)
            state = await unit.publication(identity)
            if _source_producer is not None and (
                state.source_attempt_id != _source_producer.attempt_id or not state.source_publication_sha256
            ):
                raise ConflictException("Source native binding differs", code="BULK_NATIVE_RECEIPT_CONFLICT")
            if isinstance(lease, SourceReplacementExecution) != (state.operation_kind == "replace"):
                raise ConflictException("Native operation kind differs", code="BULK_NATIVE_RECEIPT_CONFLICT")
            if state.operation_kind == "replace":
                if _source_producer is None:
                    raise ConflictException(
                        "The dataset requires its exact source producer", code="SOURCE_PUBLICATION_DENIED"
                    )
                await _source_producer.plans(unit._session)
            if state.status == "committed":
                return state
            if state.operation_kind == "replace":
                for table in state.prepared:
                    if table.reconcile_changes is not None:
                        await publish_reconcile_changes(unit._session, table.reconcile_changes)
                await unit.activate_replacement(identity)
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
            if isinstance(lease, SourceReplacementExecution):
                assert _source_producer is not None
                _source_producer.held_admission()
            elif _source_producer is not None:
                await self.queue._check(lease, _source_admission=admission)
            else:
                await self.queue._check(lease)
            return await unit.commit(identity)
