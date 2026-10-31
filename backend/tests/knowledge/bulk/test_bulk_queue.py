# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta

import pytest
from pyfly.kernel import ConflictException
from test_bulk_native import bulk as bulk
from test_bulk_native import request

from koinon.jobs.service import JobService
from koinon.knowledge.bulk.dtos import BulkAction
from koinon.knowledge.bulk.entities import now
from koinon.knowledge.bulk.queue import BulkQueue


async def queued(env, key):
    batch = await env.service.create("issuer|editor", "north", request(env.target), "create-" + key)
    item = (await env.service.items("issuer|editor", "north", batch.id)).items[0]
    await env.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    current = await env.service.get("issuer|editor", "north", batch.id)
    await env.service.submit(
        "issuer|editor", "north", batch.id, BulkAction(expected_revision=current.revision), "submit"
    )
    return batch.id, item.id


async def test_kind_filter_same_worker_generation_fence_and_restart_preserve_stable_item_identity(bulk):
    batch, item = await queued(bulk, "one")
    jobs = bulk.context.get_bean(JobService)
    other = await jobs.submit("north", bulk.target["parent_id"], "another.kind", {}, "unrelated")
    queue = bulk.context.get_bean(BulkQueue)
    first = await queue.claim("same-worker")
    assert first.item_id == item and first.batch_id == batch and first.attempt == 1
    job = await jobs.repository.find_by_id(first.job_id)
    job.lease_until = now() - timedelta(seconds=1)
    await jobs.repository.save(job)
    second = await queue.claim("same-worker")
    assert second.item_id == first.item_id and second.attempt == 2
    with pytest.raises(ConflictException):
        await queue.check(first)
    await queue.check(second)
    assert (await jobs.repository.find_by_id(other.id)).status == "queued"


async def test_global_concurrency_is_durable_and_cancellation_fences_claimed_attempt(bulk):
    await queued(bulk, "one")
    await queued(bulk, "two")
    bulk.service.settings.max_workers_global = 1
    queue = bulk.context.get_bean(BulkQueue)
    first = await queue.claim("worker")
    assert first is not None and await queue.claim("other") is None
    before = await bulk.service.get("issuer|editor", "north", first.batch_id)
    await bulk.service.cancel(
        "issuer|editor", "north", first.batch_id, BulkAction(expected_revision=before.revision), "cancel"
    )
    with pytest.raises(ConflictException):
        await queue.check(first)
    assert await queue.claim("other") is not None


async def test_cancel_resolves_a_winning_native_commit_without_replaying_processing_or_relabelling_success(
    bulk,
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.knowledge.bulk.ports import NativeCommit, NativeObservation
    from koinon.knowledge.bulk.repositories import BulkRepository

    batch_id, item_id = await queued(bulk, "winner")
    lease = await bulk.context.get_bean(BulkQueue).claim("worker")
    records = bulk.context.get_bean(BulkRepository)
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        item = await records.item(batch_id, item_id, lock=True)
        item.native_workspace_id = bulk.target["workspace_id"]
        await records.flush()
    receipt = NativeCommit(
        domain="canon",
        native_workspace_id=bulk.target["workspace_id"],
        native_source_id="native",
        native_asset_id="native",
        sha256=lease.sha256,
        size_bytes=lease.size_bytes,
        source_version_id="v1",
        extraction_id="e1",
    )

    async def ack(_lease, _receipt):
        from dataclasses import asdict

        assert _receipt == receipt
        item = await records.item(batch_id, item_id, lock=True)
        job = await records.job(lease.job_id)
        item.status = "succeeded"
        item.native_id = _receipt.native_asset_id
        item.receipt_json = asdict(_receipt)
        job.status = "succeeded"
        await records.flush()

    native = SimpleNamespace(
        inspect=AsyncMock(return_value=NativeObservation("committed", receipt)),
        acknowledge_committed=AsyncMock(side_effect=ack),
        execute=AsyncMock(),
        reserve=AsyncMock(),
    )
    bulk.service.intakes = SimpleNamespace(get=lambda: native)
    current = await bulk.service.get("issuer|editor", "north", batch_id)
    cancelled = await bulk.service.cancel(
        "issuer|editor", "north", batch_id, BulkAction(expected_revision=current.revision), "cancel"
    )
    assert cancelled.status == "succeeded" and cancelled.cancellation_requested is True
    native.execute.assert_not_awaited()
    native.reserve.assert_not_awaited()
    native.acknowledge_committed.assert_awaited_once()


async def test_cancel_unknown_native_outcome_remains_inspectable_and_never_claims_success(bulk):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.knowledge.bulk.repositories import BulkRepository

    batch_id, item_id = await queued(bulk, "unknown")
    await bulk.context.get_bean(BulkQueue).claim("worker")
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        item = await records.item(batch_id, item_id, lock=True)
        item.native_workspace_id = bulk.target["workspace_id"]
        await records.flush()
    bulk.service.intakes = SimpleNamespace(
        get=lambda: SimpleNamespace(inspect=AsyncMock(side_effect=OSError("private driver error")))
    )
    current = await bulk.service.get("issuer|editor", "north", batch_id)
    cancelled = await bulk.service.cancel(
        "issuer|editor", "north", batch_id, BulkAction(expected_revision=current.revision), "cancel"
    )
    assert cancelled.status == "reconciling" and cancelled.cancellation_requested is True
    assert (await bulk.service.items("issuer|editor", "north", batch_id)).items[
        0
    ].error_code == "BULK_CANCELLATION_UNKNOWN"


async def test_generic_worker_never_claims_or_expires_native_bulk_jobs(bulk):
    batch, item = await queued(bulk, "generic-isolation")
    jobs = bulk.context.get_bean(JobService)
    assert await jobs.claim("generic-worker") is None
    lease = await bulk.context.get_bean(BulkQueue).claim("bulk-worker")
    assert lease.item_id == item and lease.batch_id == batch
    job = await jobs.repository.find_by_id(lease.job_id)
    job.lease_until = now() - timedelta(seconds=1)
    job.attempts = job.max_attempts
    await jobs.repository.save(job)
    assert await jobs.claim("generic-worker") is None
    assert (await jobs.repository.find_by_id(lease.job_id)).status == "running"


async def test_generic_cancel_requires_bulk_lifecycle_and_cannot_orphan_item_status(bulk):
    from koinon.jobs.management import JobManagementService

    batch, item = await queued(bulk, "cancel-route")
    jobs = bulk.context.get_bean(JobService)
    job = (await jobs.repository.find_all(kind="knowledge.bulk.intake"))[0]
    with pytest.raises(ConflictException) as denied:
        await bulk.context.get_bean(JobManagementService).cancel("issuer|editor", "north", job.id)
    assert denied.value.code == "BULK_LIFECYCLE_REQUIRED"
    assert (await jobs.repository.find_by_id(job.id)).status == "queued"
    assert (await bulk.service.items("issuer|editor", "north", batch)).items[0].id == item
    assert (await bulk.service.get("issuer|editor", "north", batch)).status == "queued"


async def test_native_ack_binds_exact_existing_commit_atomically_without_reprocessing(bulk):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from koinon.knowledge.bulk.native import NativeBulkIntake
    from koinon.knowledge.bulk.ports import NativeCommit, NativeObservation
    from koinon.knowledge.entities import DomainBinding
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings

    batch_id, item_id = await queued(bulk, "native-ack")
    queue = bulk.context.get_bean(BulkQueue)
    lease = await queue.claim("worker")
    bindings = bulk.context.get_bean(DomainBindingRepository)
    workspace = str(uuid4())
    await bindings.save(
        DomainBinding(
            id=str(uuid4()),
            tenant_id="north",
            catalog_id=bulk.target["workspace_id"],
            workspace_id=bulk.target["workspace_id"],
            domain="canon",
            entity_kind="workspace",
            native_id=workspace,
            native_workspace_id=workspace,
            created_by="issuer|editor",
        )
    )
    facade = KnowledgeFacade(bulk.catalog, bindings, SimpleNamespace(), KnowledgeSettings())
    port = bulk.context.get_bean(NativeBulkIntake)
    port.facades = SimpleNamespace(get=lambda: facade)
    await port.reserve(lease)
    receipt = NativeCommit(
        domain="canon",
        native_workspace_id=workspace,
        native_source_id=str(uuid4()),
        native_asset_id=str(uuid4()),
        sha256=lease.sha256,
        size_bytes=lease.size_bytes,
        source_version_id=str(uuid4()),
        extraction_id=str(uuid4()),
    )
    port.inspect = AsyncMock(return_value=NativeObservation("committed", receipt))
    await port.acknowledge(lease, receipt)
    result = (await bulk.service.items("issuer|editor", "north", batch_id)).items[0]
    assert result.id == item_id and result.status == "succeeded"
    assert (
        result.source_version_id == receipt.source_version_id
        and result.extraction_id == receipt.extraction_id
    )
    assert (await bulk.catalog.get("issuer|editor", "north", lease.asset_id)).status == "ready"
    asset_binding = await facade.binding("north", lease.asset_id, "canon")
    assert asset_binding.native_id == receipt.native_asset_id
    job = await bulk.context.get_bean(JobService).repository.find_by_id(lease.job_id)
    assert job.status == "succeeded" and job.lease_until is None and job.progress == 100
    port.inspect.reset_mock()
    await port.acknowledge_committed(lease, receipt)
    port.inspect.assert_not_awaited()
    assert len(await bindings.find_all(tenant_id="north", domain="canon")) == 3


@pytest.mark.parametrize("archive_before_ack", [False, True])
async def test_dataset_tables_are_reserved_before_native_work_and_ack_uses_exact_reserved_ids(
    bulk, archive_before_ack
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.knowledge.bulk.dataset_dtos import DatasetReservation
    from koinon.knowledge.bulk.dtos import FileBatchCreate
    from koinon.knowledge.bulk.native import NativeBulkIntake
    from koinon.knowledge.bulk.ports import NativeCommit, NativeObservation, NativeTableCommit
    from koinon.knowledge.bulk.repositories import BulkRepository
    from koinon.knowledge.bulk.structured_dtos import StructuredTablePlan
    from koinon.knowledge.connections.entities import KnowledgeConnection
    from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
    from koinon.knowledge.entities import DomainBinding
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings

    await bulk.context.get_bean(KnowledgeConnectionRepository).save(
        KnowledgeConnection(
            id="structured-connection",
            tenant_id="north",
            workspace_id=bulk.target["workspace_id"],
            scope_key=bulk.target["workspace_id"],
            domain="structured",
            role="structured.embedding",
            mode="provider",
            provider_id="embedding-provider",
            model_id="embedding",
            dimensions=768,
            embedding_fingerprint="f" * 64,
            created_by="issuer|editor",
            updated_by="issuer|editor",
        )
    )
    body = request(bulk.target).model_dump(mode="json")
    body["items"][0]["mode"] = "dataset"
    batch = await bulk.service.create(
        "issuer|editor", "north", FileBatchCreate.model_validate(body), "dataset"
    )
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    current = await bulk.service.get("issuer|editor", "north", batch.id)
    await bulk.service.submit(
        "issuer|editor", "north", batch.id, BulkAction(expected_revision=current.revision), "submit"
    )
    queue = bulk.context.get_bean(BulkQueue)
    lease = await queue.claim("dataset-worker")
    bindings = bulk.context.get_bean(DomainBindingRepository)
    workspace = str(uuid4())
    await bindings.save(
        DomainBinding(
            id=str(uuid4()),
            tenant_id="north",
            catalog_id=bulk.target["workspace_id"],
            workspace_id=bulk.target["workspace_id"],
            domain="structured",
            entity_kind="workspace",
            native_id=workspace,
            native_workspace_id=workspace,
            created_by="issuer|editor",
        )
    )
    facade = KnowledgeFacade(bulk.catalog, bindings, SimpleNamespace(), KnowledgeSettings())
    port = bulk.context.get_bean(NativeBulkIntake)
    port.facades = SimpleNamespace(get=lambda: facade)
    await port.reserve(lease)
    plan = (StructuredTablePlan(ordinal=0, table_id=uuid4(), snapshot_id=uuid4(), name="facts"),)
    reserved = await queue.reserve_tables(lease, plan)
    assert reserved[0].catalog_table_id and (await queue.reserve_tables(lease, plan)) == reserved
    records = bulk.context.get_bean(BulkRepository)
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        row = await records.item(batch.id, item.id)
        reservation = DatasetReservation.stored(row.reservation_json)
    table = reserved[0]
    receipt = NativeCommit(
        domain="structured",
        native_workspace_id=workspace,
        native_source_id=str(reservation.native_dataset_id),
        native_asset_id=str(reservation.native_dataset_id),
        sha256=lease.sha256,
        size_bytes=lease.size_bytes,
        object_key="raw/private",
        file_version_id=reservation.catalog_file_version_id,
        native_file_id=str(reservation.native_file_id),
        tables=(
            NativeTableCommit(table.catalog_table_id, str(table.table_id), str(table.snapshot_id), 2, 1),
        ),
    )
    port.inspect = AsyncMock(return_value=NativeObservation("committed", receipt))
    if archive_before_ack:
        from koinon.catalog.errors import AccessDenied

        await bulk.catalog.update("issuer|editor", "north", table.catalog_table_id, {"status": "archived"})
        with pytest.raises(AccessDenied):
            await queue.check(lease)
        with pytest.raises(AccessDenied):
            await port.acknowledge(lease, receipt)
        port.inspect.assert_not_awaited()
        assert len(await bindings.find_all(tenant_id="north", domain="structured")) == 1
        return
    await port.acknowledge(lease, receipt)
    result = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    assert result.status == "succeeded" and result.table_ids == [table.catalog_table_id]
    assert (await bulk.catalog.get("issuer|editor", "north", result.file_version_id)).status == "ready"
    assert (await facade.binding("north", table.catalog_table_id, "structured")).native_id == str(
        table.table_id
    )
    await port.acknowledge_committed(lease, receipt)
    assert len(await bindings.find_all(tenant_id="north", domain="structured")) == 5
