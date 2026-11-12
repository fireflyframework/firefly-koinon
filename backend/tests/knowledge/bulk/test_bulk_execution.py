# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

from koinon.knowledge.bulk.execution import BulkExecutor
from koinon.knowledge.bulk.ports import NativeCommit, NativeObservation
from koinon.knowledge.bulk.queue import BulkOriginal


def setup(status):
    content = b"original"
    lease = SimpleNamespace(
        subject="issuer|editor",
        token_id="original-token",
        sha256=sha256(content).hexdigest(),
        size_bytes=len(content),
    )
    receipt = NativeCommit(
        domain="canon",
        native_workspace_id="workspace",
        native_source_id="native",
        native_asset_id="native",
        sha256=lease.sha256,
        size_bytes=len(content),
        source_version_id="version",
        extraction_id="extraction",
    )
    queue = SimpleNamespace(
        check=AsyncMock(),
        original=AsyncMock(
            return_value=BulkOriginal(object_key="opaque", size_bytes=len(content), sha256=lease.sha256)
        ),
        failed=AsyncMock(),
    )
    native = SimpleNamespace(
        reserve=AsyncMock(),
        inspect=AsyncMock(return_value=NativeObservation(status, receipt if status == "committed" else None)),
        inspect_committed=AsyncMock(
            return_value=NativeObservation(status, receipt if status == "committed" else None)
        ),
        execute=AsyncMock(return_value=receipt),
        acknowledge=AsyncMock(),
    )
    store = SimpleNamespace(read=AsyncMock(return_value=content))
    return BulkExecutor(queue, store, SimpleNamespace(get=lambda: native)), queue, native, store, lease


async def test_native_commit_primary_ack_loss_recovers_receipt_without_original_parse_embed_or_native_write():
    worker, queue, native, store, lease = setup("committed")
    await worker.execute(lease)
    store.read.assert_not_awaited()
    native.execute.assert_not_awaited()
    native.acknowledge.assert_awaited_once()
    queue.failed.assert_not_awaited()


async def test_admitted_unknown_native_effect_is_inspectable_and_never_automatically_replayed():
    worker, queue, native, store, lease = setup("admitted")
    await worker.execute(lease)
    native.execute.assert_not_awaited()
    native.acknowledge.assert_not_awaited()
    store.read.assert_not_awaited()
    assert queue.failed.call_args.kwargs["unknown"] is True


async def test_absent_native_operation_runs_once_then_acknowledges_and_never_retries_unknown_failure():
    worker, queue, native, store, lease = setup("absent")
    await worker.execute(lease)
    native.execute.assert_awaited_once()
    native.acknowledge.assert_awaited_once()
    assert queue.check.await_count >= 2
    worker, queue, native, store, lease = setup("absent")
    native.execute.side_effect = TimeoutError("sensitive raw provider error")
    await worker.execute(lease)
    native.execute.assert_awaited_once()
    native.acknowledge.assert_not_awaited()
    assert queue.failed.call_args.kwargs == {"code": "BULK_PROCESSING_FAILED", "unknown": True}


async def test_complete_prepared_native_receipt_finalizes_metadata_without_original_or_model_replay():
    worker, queue, native, store, lease = setup("prepared")
    native.finalize_prepared = AsyncMock(return_value=setup("committed")[2].inspect.return_value.receipt)
    await worker.execute(lease)
    native.finalize_prepared.assert_awaited_once_with(lease)
    native.execute.assert_not_awaited()
    store.read.assert_not_awaited()
    native.acknowledge.assert_awaited_once()
    queue.failed.assert_not_awaited()


async def test_cancelled_source_recovers_only_existing_receipt_without_native_reservation():
    from pyfly.kernel import ConflictException

    worker, queue, native, store, lease = setup("committed")
    queue.check.side_effect = ConflictException("Cancelled", code="SOURCE_PUBLICATION_DENIED")
    queue.reconcile_source = AsyncMock()
    native.settle_source_receipt = AsyncMock()
    await worker.execute(lease)
    native.settle_source_receipt.assert_awaited_once_with(lease, native.inspect.return_value.receipt)
    native.reserve.assert_not_awaited()
    native.execute.assert_not_awaited()
    store.read.assert_not_awaited()
    queue.failed.assert_not_awaited()


async def test_cancelled_source_unknown_outcome_never_finalizes_or_reprocesses():
    from pyfly.kernel import ConflictException

    for status in ("absent", "prepared", "admitted", "failed"):
        worker, queue, native, store, lease = setup(status)
        queue.check.side_effect = ConflictException("Cancelled", code="SOURCE_PUBLICATION_DENIED")
        queue.reconcile_source = AsyncMock()
        native.settle_source_receipt = AsyncMock()
        native.finalize_prepared = AsyncMock()
        await worker.execute(lease)
        native.reserve.assert_not_awaited()
        native.execute.assert_not_awaited()
        native.finalize_prepared.assert_not_awaited()
        native.settle_source_receipt.assert_not_awaited()
        store.read.assert_not_awaited()
        assert queue.failed.call_args.kwargs == {"code": "BULK_NATIVE_OUTCOME_UNRESOLVED", "unknown": True}


async def test_local_permission_denial_cannot_become_a_source_receipt_recovery():
    from pyfly.kernel import ConflictException
    from koinon.catalog.errors import AccessDenied

    worker, queue, native, store, lease = setup("committed")
    queue.check.side_effect = AccessDenied("Revoked", code="ACCESS_DENIED")
    queue.reconcile_source = AsyncMock(side_effect=ConflictException("Not a source", code="SOURCE_PUBLICATION_DENIED"))
    await worker.execute(lease)
    native.inspect_committed.assert_not_awaited()
    native.execute.assert_not_awaited()
    store.read.assert_not_awaited()
    assert queue.failed.call_args.kwargs == {"code": "ACCESS_DENIED", "unknown": True}
