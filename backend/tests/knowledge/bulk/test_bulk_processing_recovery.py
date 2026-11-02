# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from test_bulk_native import bulk as bulk
from test_bulk_queue import queued

from koinon.knowledge.bulk.ports import NativeObservation
from koinon.knowledge.bulk.queue import BulkQueue
from koinon.knowledge.bulk.repositories import BulkRepository


async def failed_before_native(bulk, mode="document"):
    if mode == "document":
        batch_id, item_id = await queued(bulk, "recovery")
    else:
        from test_bulk_native import request

        from koinon.knowledge.bulk.dtos import BulkAction
        from koinon.knowledge.connections.entities import KnowledgeConnection
        from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository

        await bulk.context.get_bean(KnowledgeConnectionRepository).save(
            KnowledgeConnection(
                id="structured-embedding",
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
        manifest = request(bulk.target)
        manifest = manifest.model_copy(
            update={"items": [manifest.items[0].model_copy(update={"mode": mode})]}
        )
        batch = await bulk.service.create("issuer|editor", "north", manifest, "create-recovery")
        item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
        await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
        batch = await bulk.service.get("issuer|editor", "north", batch.id)
        await bulk.service.submit(
            "issuer|editor", "north", batch.id, BulkAction(expected_revision=batch.revision), "submit"
        )
        batch_id, item_id = batch.id, item.id
    queue = bulk.context.get_bean(BulkQueue)
    lease = await queue.claim("original-worker")
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        item = await records.item(batch_id, item_id, lock=True)
        item.native_workspace_id = bulk.target["workspace_id"]
        await records.flush()
    await queue.failed(lease, code="INGEST_EXECUTION_CONTEXT_REQUIRED", unknown=True)
    native = SimpleNamespace(inspect=AsyncMock(return_value=NativeObservation("absent")))
    bulk.service.intakes = SimpleNamespace(get=lambda: native)
    records = bulk.context.get_bean(BulkRepository)
    records.workspace_matches = AsyncMock(return_value=True)
    return batch_id, item_id, lease, native


async def test_failed_retained_item_offers_explicit_absence_checked_recovery_without_replay(bulk):
    batch_id, item_id, lease, native = await failed_before_native(bulk)
    before = await bulk.service.get("issuer|editor", "north", batch_id)
    descriptor = await bulk.service.processing_recovery("issuer|editor", "north", batch_id, item_id)
    assert descriptor.native_state == "absent"
    assert descriptor.operation == "retry_processing"
    assert descriptor.batch_revision == before.revision
    assert descriptor.attempts == lease.attempt == 1 and descriptor.max_attempts == 3
    assert descriptor.checked_at is not None and descriptor.reason_code is None
    assert descriptor.job_status == "failed" and descriptor.original_receipt_state == "verified"
    after = await bulk.service.get("issuer|editor", "north", batch_id)
    assert after == before
    native.inspect.assert_awaited_once()
    assert await bulk.context.get_bean(BulkQueue).claim("another-worker") is None


async def test_explicit_recovery_preserves_job_original_attempts_failure_audit_and_old_lease_fence(bulk):
    from pyfly.kernel import ConflictException

    from koinon.knowledge.bulk.dtos import BulkRecoveryAction

    batch_id, item_id, old, native = await failed_before_native(bulk)
    descriptor = await bulk.service.processing_recovery("issuer|editor", "north", batch_id, item_id)
    body = BulkRecoveryAction(expected_revision=descriptor.batch_revision, operation="retry_processing")
    recovered = await bulk.service.recover_processing(
        "issuer|editor", "north", batch_id, item_id, body, "recover"
    )
    assert recovered.status == "queued" and recovered.revision == descriptor.batch_revision + 1
    queue = bulk.context.get_bean(BulkQueue)
    with pytest.raises(ConflictException):
        await queue.check(old)
    from koinon.jobs.service import JobService

    assert await bulk.context.get_bean(JobService).claim("ordinary-worker") is None
    new = await queue.claim("new-worker")
    assert new.recovery_operation == "retry_processing"
    assert new.job_id == old.job_id and new.item_id == old.item_id and new.attempt == old.attempt + 1
    assert new.source_id == old.source_id and new.asset_id == old.asset_id and new.sha256 == old.sha256
    await queue.check(new)
    native.inspect.reset_mock()
    replay = await bulk.service.recover_processing(
        "issuer|editor", "north", batch_id, item_id, body, "recover"
    )
    assert replay.status == "running"
    native.inspect.assert_not_awaited()
    await queue.check(new)
    audit = await bulk.catalog.audit_repository.find_all(action="knowledge.bulk.recovery_requested")
    assert len(audit) == 1 and audit[0].details["previous_error_code"] == "INGEST_EXECUTION_CONTEXT_REQUIRED"
    assert audit[0].details["attempts"] == 1


@pytest.mark.parametrize("state", ["admitted", "unknown"])
async def test_unknown_native_effect_never_offers_or_requeues_processing(bulk, state):
    from pyfly.kernel import ConflictException

    from koinon.knowledge.bulk.dtos import BulkRecoveryAction

    batch_id, item_id, _, native = await failed_before_native(bulk)
    if state == "unknown":
        native.inspect.side_effect = TimeoutError("Never expose this raw private detail")
    else:
        native.inspect.return_value = NativeObservation(state)
    descriptor = await bulk.service.processing_recovery("issuer|editor", "north", batch_id, item_id)
    assert descriptor.native_state == state and descriptor.operation is None
    assert descriptor.reason_code == "BULK_NATIVE_OUTCOME_UNRESOLVED"
    assert "private" not in descriptor.model_dump_json()
    with pytest.raises(ConflictException):
        await bulk.service.recover_processing(
            "issuer|editor",
            "north",
            batch_id,
            item_id,
            BulkRecoveryAction(expected_revision=descriptor.batch_revision, operation="retry_processing"),
            "recover",
        )
    assert (await bulk.service.get("issuer|editor", "north", batch_id)).status == "reconciling"
    assert await bulk.context.get_bean(BulkQueue).claim("new-worker") is None


@pytest.mark.parametrize(
    "change,reason",
    [
        ("cancelled", "BULK_RECOVERY_UNAVAILABLE"),
        ("expired", "BULK_RECOVERY_UNAVAILABLE"),
        ("running", "BULK_RECOVERY_BUSY"),
        ("owner", "BULK_RECOVERY_BUSY"),
        ("expired_lease", "BULK_RECOVERY_BUSY"),
        ("attempts", "BULK_RETRY_EXHAUSTED"),
    ],
)
async def test_terminal_expiration_cancel_attempt_and_owner_fences(bulk, change, reason):
    from datetime import timedelta

    from koinon.knowledge.bulk.entities import now

    batch_id, item_id, lease, native = await failed_before_native(bulk)
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        batch = await records.scoped("north", "issuer|editor", batch_id, lock=True)
        job = await records.job(lease.job_id)
        if change == "cancelled":
            batch.cancelled = True
        if change == "expired":
            batch.expires_at = now() - timedelta(seconds=1)
        if change == "running":
            job.status = "running"
        if change == "owner":
            job.worker_id = "old-worker"
        if change == "expired_lease":
            job.lease_until = now() - timedelta(seconds=1)
        if change == "attempts":
            job.attempts = job.max_attempts
        await records.flush()
    descriptor = await bulk.service.processing_recovery("issuer|editor", "north", batch_id, item_id)
    assert descriptor.operation is None and descriptor.reason_code == reason
    if change != "attempts":
        native.inspect.assert_not_awaited()


async def test_get_observation_is_not_post_admission_and_changed_native_state_stops_requeue(bulk):
    from pyfly.kernel import ConflictException

    from koinon.knowledge.bulk.dtos import BulkRecoveryAction

    batch_id, item_id, _, native = await failed_before_native(bulk)
    descriptor = await bulk.service.processing_recovery("issuer|editor", "north", batch_id, item_id)
    native.inspect.return_value = NativeObservation("admitted")
    with pytest.raises(ConflictException) as error:
        await bulk.service.recover_processing(
            "issuer|editor",
            "north",
            batch_id,
            item_id,
            BulkRecoveryAction(expected_revision=descriptor.batch_revision, operation="retry_processing"),
            "recover",
        )
    assert error.value.code == "BULK_NATIVE_OUTCOME_UNRESOLVED"
    assert await bulk.context.get_bean(BulkQueue).claim("new-worker") is None


async def test_revoked_membership_and_different_token_cannot_observe_or_resume_original_batch(bulk):
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.bulk.dtos import BulkRecoveryAction

    batch_id, item_id, _, native = await failed_before_native(bulk)
    current = await bulk.service.get("issuer|editor", "north", batch_id)
    with (
        SecurityContextHolder.using(
            SecurityContext(user_id="editor", attributes={"koinon_token_id": "other"})
        ),
        pytest.raises(AccessDenied),
    ):
        await bulk.service.processing_recovery("issuer|editor", "north", batch_id, item_id)
    member = await bulk.members.find_by_id("editor")
    member.active = False
    await bulk.members.save(member)
    with pytest.raises(AccessDenied):
        await bulk.service.recover_processing(
            "issuer|editor",
            "north",
            batch_id,
            item_id,
            BulkRecoveryAction(expected_revision=current.revision, operation="retry_processing"),
            "recover",
        )
    native.inspect.assert_not_awaited()


@pytest.mark.parametrize("change", ["operation", "key", "revision", "attempt", "malformed", "missing"])
async def test_forged_malformed_or_stale_pending_intent_cannot_claim_a_new_worker(bulk, change):
    from pyfly.kernel import ConflictException

    from koinon.knowledge.bulk.dtos import BulkRecoveryAction

    batch_id, item_id, old, _ = await failed_before_native(bulk)
    before = await bulk.service.get("issuer|editor", "north", batch_id)
    await bulk.service.recover_processing(
        "issuer|editor",
        "north",
        batch_id,
        item_id,
        BulkRecoveryAction(expected_revision=before.revision, operation="retry_processing"),
        "recover",
    )
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        job = await records.job(old.job_id)
        result = dict(job.result)
        intent = dict(result["bulk_processing_recovery"])
        if change == "operation":
            intent["operation"] = "finalize_publication"
        if change == "key":
            intent["key_hash"] = "0" * 64
        if change == "revision":
            intent["expected_revision"] = 1
        if change == "attempt":
            intent["starting_attempt"] = 3
        result["bulk_processing_recovery"] = None if change == "malformed" else intent
        job.result = None if change == "missing" else result
        await records.flush()
    with pytest.raises(ConflictException) as error:
        await bulk.context.get_bean(BulkQueue).claim("new-worker")
    assert error.value.code == "BULK_RECOVERY_STATE_CHANGED"


async def test_worker_never_reinterprets_finalization_as_new_processing_after_native_drift():
    from test_bulk_execution import setup

    worker, queue, native, store, lease = setup("absent")
    lease.recovery_operation = "finalize_publication"
    await worker.execute(lease)
    store.read.assert_not_awaited()
    native.execute.assert_not_awaited()
    queue.original.assert_not_awaited()
    native.acknowledge.assert_not_awaited()
    assert queue.failed.call_args.kwargs == {"code": "BULK_RECOVERY_STATE_CHANGED", "unknown": True}


async def test_recovery_intent_survives_real_queue_expiration_and_reclaim_without_reset(bulk):
    from datetime import timedelta

    from pyfly.kernel import ConflictException

    from koinon.knowledge.bulk.dtos import BulkRecoveryAction
    from koinon.knowledge.bulk.entities import now

    batch_id, item_id, old, _ = await failed_before_native(bulk)
    before = await bulk.service.get("issuer|editor", "north", batch_id)
    await bulk.service.recover_processing(
        "issuer|editor",
        "north",
        batch_id,
        item_id,
        BulkRecoveryAction(expected_revision=before.revision, operation="retry_processing"),
        "recover",
    )
    queue = bulk.context.get_bean(BulkQueue)
    second = await queue.claim("second-worker")
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        job = await records.job(old.job_id)
        job.lease_until = now() - timedelta(seconds=1)
        await records.flush()
    third = await queue.claim("third-worker")
    assert third.attempt == 3 and third.recovery_operation == second.recovery_operation == "retry_processing"
    await queue.check(third)
    with pytest.raises(ConflictException):
        await queue.check(second)


async def test_prepared_dataset_offers_only_finalization_and_worker_does_not_read_original_or_models(bulk):
    from koinon.knowledge.bulk.dtos import BulkRecoveryAction
    from koinon.knowledge.bulk.execution import BulkExecutor
    from koinon.knowledge.bulk.ports import NativeCommit

    batch_id, item_id, old, native = await failed_before_native(bulk, "dataset")
    native.inspect.return_value = NativeObservation("prepared")
    descriptor = await bulk.service.processing_recovery("issuer|editor", "north", batch_id, item_id)
    assert descriptor.operation == "finalize_publication"
    await bulk.service.recover_processing(
        "issuer|editor",
        "north",
        batch_id,
        item_id,
        BulkRecoveryAction(expected_revision=descriptor.batch_revision, operation="finalize_publication"),
        "finish",
    )
    queue = bulk.context.get_bean(BulkQueue)
    new = await queue.claim("new-worker")
    assert new.recovery_operation == "finalize_publication" and new.attempt == 2
    native.reserve = AsyncMock()
    native.finalize_prepared = AsyncMock(
        return_value=NativeCommit(
            domain="structured",
            native_workspace_id=bulk.target["workspace_id"],
            native_source_id="native",
            native_asset_id="native",
            sha256=old.sha256,
            size_bytes=old.size_bytes,
        )
    )
    native.acknowledge = AsyncMock()
    native.execute = AsyncMock(side_effect=AssertionError("Must not process again"))
    storage = SimpleNamespace(read=AsyncMock(side_effect=AssertionError("Must not fetch original")))
    await BulkExecutor(queue, storage, SimpleNamespace(get=lambda: native)).execute(new)
    native.finalize_prepared.assert_awaited_once_with(new)
    native.acknowledge.assert_awaited_once()
    native.execute.assert_not_awaited()
    storage.read.assert_not_awaited()


async def test_committed_recovery_uses_original_context_through_real_primary_ack_without_reprocessing(bulk):
    from uuid import uuid4

    from pyfly.security.context_holder import SecurityContextHolder

    from koinon.knowledge.bulk.dtos import BulkRecoveryAction
    from koinon.knowledge.bulk.native import NativeBulkIntake
    from koinon.knowledge.bulk.ports import NativeCommit
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings

    batch_id, item_id, old, _ = await failed_before_native(bulk)
    receipt = NativeCommit(
        domain="canon",
        native_workspace_id=bulk.target["workspace_id"],
        native_source_id=str(uuid4()),
        native_asset_id=str(uuid4()),
        sha256=old.sha256,
        size_bytes=old.size_bytes,
        source_version_id=str(uuid4()),
        extraction_id=str(uuid4()),
    )
    contexts = []

    async def inspect(lease):
        context = SecurityContextHolder.get_context()
        assert context.attributes["iss"] == "issuer" and context.attributes["sub"] == "editor"
        contexts.append(context)
        return NativeObservation("committed", receipt)

    port = bulk.context.get_bean(NativeBulkIntake)
    facade = KnowledgeFacade(
        bulk.catalog, bulk.context.get_bean(DomainBindingRepository), SimpleNamespace(), KnowledgeSettings()
    )
    port.facades, port.inspect = SimpleNamespace(get=lambda: facade), inspect
    bulk.service.intakes = SimpleNamespace(get=lambda: port)
    before = await bulk.service.get("issuer|editor", "north", batch_id)
    result = await bulk.service.recover_processing(
        "issuer|editor",
        "north",
        batch_id,
        item_id,
        BulkRecoveryAction(expected_revision=before.revision, operation="acknowledge_commit"),
        "acknowledge",
    )
    assert result.status == "succeeded" and len(contexts) == 3
    assert SecurityContextHolder.get_context() is None
    assert (await bulk.service.items("issuer|editor", "north", batch_id)).items[
        0
    ].source_version_id == receipt.source_version_id
    assert await bulk.context.get_bean(BulkQueue).claim("another-worker") is None
