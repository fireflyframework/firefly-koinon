# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Only a current terminal unpublished native failure can authorize a confirmed retry."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_bulk_native import bulk as bulk
from test_bulk_processing_recovery import failed_before_native

from koinon.knowledge.bulk.dtos import BulkRecoveryAction
from koinon.knowledge.bulk.failed_native import failed_native_proof
from koinon.knowledge.bulk.ports import NativeObservation
from koinon.knowledge.bulk.queue import BulkQueue
from koinon.knowledge.bulk.recovery_intent import NativeFailureProof


@pytest.mark.parametrize(
    "invalid", [None, "old", "admitted", "same_time", "published", "head_changed", "foreign_version"]
)
async def test_failed_proof_requires_current_terminal_failure_and_unchanged_head(invalid):
    start = datetime(2026, 11, 2, tzinfo=UTC)
    failure = start + timedelta(seconds=32)
    event = dict(id="event", version_id="version", status="failed", extraction_id=None, created_at=failure)
    if invalid == "old":
        event["created_at"] = start - timedelta(seconds=1)
    if invalid == "admitted":
        event["status"] = "admitted"
    if invalid == "foreign_version":
        event["version_id"] = "other-version"
    head = dict(version_id=None, extraction_id=None)
    if invalid == "head_changed":
        head["version_id"] = "foreign"
    events = [event, {**event, "id": "ambiguous"}] if invalid == "same_time" else [event]
    unit = SimpleNamespace(first=AsyncMock(return_value=head), all=AsyncMock(return_value=events))
    version = dict(id="version", source_id="source", predecessor_id=None, expected_extraction_id=None)
    lease = SimpleNamespace(attempt=2, attempt_started_at=start, recovery_failure=None)
    result = await failed_native_proof(unit, "scope", version, lease, published=invalid == "published")
    if invalid is None:
        assert result == NativeFailureProof(
            version_id="version",
            event_id="event",
            failed_at=failure,
            attempt=2,
            attempt_started_at=start,
        )
    else:
        assert result is None


async def test_failed_native_retry_is_explicit_retains_original_and_advances_same_job(bulk):
    batch_id, item_id, old, native = await failed_before_native(bulk)
    proof = NativeFailureProof(
        version_id="version",
        event_id="event",
        failed_at=old.attempt_started_at + timedelta(seconds=1),
        attempt=old.attempt,
        attempt_started_at=old.attempt_started_at,
    )
    native.inspect.return_value = NativeObservation("failed", failure=proof)
    observed = await bulk.service.processing_recovery(old.subject, old.tenant_id, batch_id, item_id)
    assert observed.native_state == "failed" and observed.operation == "retry_processing"
    queue = bulk.context.get_bean(BulkQueue)
    assert await queue.claim("automatic") is None
    before = await bulk.service.items(old.subject, old.tenant_id, batch_id)
    body = BulkRecoveryAction(expected_revision=observed.batch_revision, operation="retry_processing")
    await bulk.service.recover_processing(
        old.subject, old.tenant_id, batch_id, item_id, body, "explicit-failed"
    )
    lease = await queue.claim("confirmed")
    assert lease.job_id == old.job_id and lease.source_id == old.source_id
    assert lease.sha256 == old.sha256 and lease.size_bytes == old.size_bytes
    assert lease.attempt == old.attempt + 1 and lease.recovery_failure == proof
    after = await bulk.service.items(old.subject, old.tenant_id, batch_id)
    assert after.items[0].sha256 == before.items[0].sha256
    assert after.items[0].asset_id == before.items[0].asset_id


@pytest.mark.parametrize("confirmation", ["none", "match", "changed", "forged"])
async def test_failed_native_processing_never_runs_without_the_exact_confirmed_failure(confirmation):
    from test_bulk_execution import setup

    worker, queue, native, store, lease = setup("absent")
    start = datetime(2026, 11, 2, tzinfo=UTC)
    proof = NativeFailureProof(
        version_id="version", event_id="event", failed_at=start, attempt=1, attempt_started_at=start
    )
    native.inspect.return_value = NativeObservation("failed", failure=proof)
    lease.recovery_operation = "retry_processing" if confirmation in {"match", "changed"} else None
    lease.recovery_failure = proof if confirmation != "none" else None
    if confirmation == "changed":
        native.inspect.return_value = NativeObservation(
            "failed", failure=proof.model_copy(update={"event_id": "other"})
        )
    await worker.execute(lease)
    if confirmation == "match":
        native.execute.assert_awaited_once()
        native.acknowledge.assert_awaited_once()
        queue.failed.assert_not_awaited()
    else:
        native.execute.assert_not_awaited()
        store.read.assert_not_awaited()
        queue.failed.assert_awaited_once()


async def test_old_confirmed_failure_is_only_usable_by_its_next_live_worker_not_a_later_failed_attempt():
    start = datetime(2026, 11, 2, tzinfo=UTC)
    proof = NativeFailureProof(
        version_id="version",
        event_id="event",
        failed_at=start + timedelta(seconds=1),
        attempt=1,
        attempt_started_at=start,
    )
    version = dict(id="version", source_id="source", predecessor_id=None, expected_extraction_id=None)
    event = dict(
        id="event", version_id="version", status="failed", extraction_id=None, created_at=proof.failed_at
    )
    unit = SimpleNamespace(
        first=AsyncMock(return_value=dict(version_id=None, extraction_id=None)),
        all=AsyncMock(return_value=[event]),
    )
    lease = SimpleNamespace(
        attempt=2,
        attempt_started_at=start + timedelta(seconds=10),
        recovery_failure=proof,
        expires_at=start + timedelta(minutes=5),
    )
    assert await failed_native_proof(unit, "scope", version, lease) == proof
    lease.expires_at = None
    assert await failed_native_proof(unit, "scope", version, lease) is None
    event["id"] = "next-failure"
    event["created_at"] = start + timedelta(seconds=20)
    current = await failed_native_proof(unit, "scope", version, lease)
    assert current.attempt == 2 and current.event_id == "next-failure"


def test_caller_cannot_assert_a_native_failure_in_the_recovery_body():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BulkRecoveryAction.model_validate(
            {
                "expected_revision": 1,
                "operation": "retry_processing",
                "native_failure": {"event_id": "forged"},
            }
        )


async def test_membership_revocation_after_failure_inspection_blocks_explicit_recovery(bulk):
    from koinon.catalog.errors import AccessDenied

    batch_id, item_id, old, native = await failed_before_native(bulk)
    proof = NativeFailureProof(
        version_id="version",
        event_id="event",
        failed_at=old.attempt_started_at + timedelta(seconds=1),
        attempt=old.attempt,
        attempt_started_at=old.attempt_started_at,
    )
    native.inspect.return_value = NativeObservation("failed", failure=proof)
    observed = await bulk.service.processing_recovery(old.subject, old.tenant_id, batch_id, item_id)
    member = await bulk.members.find_by_id("editor")
    member.active = False
    await bulk.members.save(member)
    with pytest.raises(AccessDenied):
        await bulk.service.recover_processing(
            old.subject,
            old.tenant_id,
            batch_id,
            item_id,
            BulkRecoveryAction(expected_revision=observed.batch_revision, operation="retry_processing"),
            "revoked",
        )
    native.inspect.assert_awaited_once()
    assert await bulk.context.get_bean(BulkQueue).claim("not-admitted") is None
