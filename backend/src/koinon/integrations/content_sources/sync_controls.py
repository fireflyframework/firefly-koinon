# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Local source-control effects and immutable receipts in the caller's transaction."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import select

from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.read_authority import source_authority
from koinon.integrations.content_sources.sync_dtos import (
    ControlAction,
    SourceControlInput,
    SourceControlOutput,
)
from koinon.integrations.content_sources.sync_entities import (
    SourceControlOperation,
    SourceMappingPolicy,
    SourceSyncRun,
    SourceSyncState,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_schedule import advance_occurrence, next_occurrence
from koinon.jobs.entities import Job
from koinon.jobs.errors import JobConflict
from koinon.knowledge.bulk.entities import BulkItem

ACTIVE_RUNS = ("queued", "running", "reconciling")
RETRYABLE_RUNS = ("failed", "partial", "reconnect_required", "cancelled")


def control_digest(mapping: str, action: str, request: SourceControlInput, target: str | None, occurrence: datetime | None = None) -> str:
    payload = [mapping, action, request.model_dump(mode="json"), target]
    if occurrence is not None:
        payload.append(["scheduled", occurrence.isoformat()])
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class SyncAuthorityCapture:
    connection_revision: int
    authority_sha256: str
    policy_id: str
    policy_sha256: str


def _conflict(code="SOURCE_CONTROL_CONFLICT"):
    return JobConflict(
        "Source control changed; read current state before submitting a new command", code=code
    )


@repository(name="content_sources.controls")
class SourceControlRepository(Repository[SourceSyncState, str]):
    async def apply(
        self,
        tenant: str,
        owner: str,
        mapping_id: str,
        action: ControlAction,
        request: SourceControlInput,
        *,
        target_run_id: str | None = None,
        capture: SyncAuthorityCapture | None = None,
        at: datetime | None = None,
        _occurrence: datetime | None = None,
    ) -> SourceControlOutput:
        """Caller holds canonical tenant/destination authority before entering.

        This method never opens a transaction or makes a provider call. Connection,
        mapping, state, object and run locks are retained through receipt insertion.
        """
        request = SourceControlInput.model_validate(request.model_dump())
        if action not in {"sync", "pause", "resume", "cancel", "retry", "retire"}:
            raise _conflict()
        if (action in {"cancel", "retry"}) != (target_run_id is not None):
            raise _conflict()
        if _occurrence is not None and (action != "sync" or _occurrence.tzinfo is None or _occurrence.utcoffset() != UTC.utcoffset(_occurrence)):
            raise _conflict()
        session = self._require_session()
        # Ownership is checked before a command UUID can reveal even safe receipt metadata.
        connection = await session.scalar(
            select(PersonalSourceConnection)
            .join(SourceMapping, SourceMapping.connection_id == PersonalSourceConnection.id)
            .where(
                SourceMapping.id == mapping_id,
                SourceMapping.tenant_id == tenant,
                SourceMapping.owner == owner,
                PersonalSourceConnection.tenant_id == tenant,
                PersonalSourceConnection.owner == owner,
            )
            .with_for_update(of=PersonalSourceConnection)
            .execution_options(populate_existing=True)
        )
        if connection is None:
            raise _conflict("SOURCE_UNAVAILABLE")
        mapping = await session.scalar(
            select(SourceMapping)
            .where(
                SourceMapping.id == mapping_id,
                SourceMapping.tenant_id == tenant,
                SourceMapping.owner == owner,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if mapping is None:
            raise _conflict("SOURCE_UNAVAILABLE")
        digest = control_digest(mapping_id, action, request, target_run_id, _occurrence)
        receipt = await session.scalar(
            select(SourceControlOperation).where(
                SourceControlOperation.tenant_id == tenant,
                SourceControlOperation.owner == owner,
                SourceControlOperation.operation_id == request.operation_id,
            )
        )
        if receipt is not None:
            if receipt.payload_sha256 != digest:
                raise _conflict("IDEMPOTENCY_CONFLICT")
            return SourceControlOutput.model_validate(receipt.result_json)
        current = await session.scalar(
            select(SourceSyncState)
            .where(SourceSyncState.mapping_id == mapping_id, SourceSyncState.tenant_id == tenant)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if current is None or current.revision != request.expected_revision or mapping.status == "retired":
            raise _conflict()
        now = at or datetime.now(UTC)
        if _occurrence is not None and (current.next_run_at != _occurrence or _occurrence > now):
            raise _conflict()
        policy = await session.get(SourceMappingPolicy, current.accepted_policy_id)
        if (
            policy is None
            or policy.mapping_id != mapping_id
            or policy.tenant_id != tenant
            or policy.accepted_at is None
        ):
            raise _conflict()
        request_policy = None
        if action in {"sync", "resume", "retry"}:
            if (
                capture is None
                or connection.status != "connected"
                or connection.refresh_operation is not None
                or connection.secret_ciphertext is None
                or connection.revision != capture.connection_revision
                or policy.id != capture.policy_id
                or policy.policy_sha256 != capture.policy_sha256
                or policy.mapping_revision != mapping.revision
                or source_authority(connection)[1] != capture.authority_sha256
                or policy.authority_sha256 != capture.authority_sha256
            ):
                raise _conflict("SOURCE_AUTHORITY_CHANGED")
            request_policy = MappingReviewInput.model_validate(policy.policy_json["request"])
        if action == "retire":
            objects = list(
                (
                    await session.scalars(
                        select(SourceObject)
                        .where(SourceObject.tenant_id == tenant, SourceObject.mapping_id == mapping_id)
                        .order_by(SourceObject.id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                ).all()
            )
            for item in objects:
                if item.generation >= 2147483647:
                    raise _conflict()
                item.generation += 1
                item.state = "excluded"
                item.updated_at = now
        runs = list(
            (
                await session.scalars(
                    select(SourceSyncRun)
                    .where(
                        SourceSyncRun.tenant_id == tenant,
                        SourceSyncRun.mapping_id == mapping_id,
                        SourceSyncRun.status.in_(ACTIVE_RUNS),
                    )
                    .order_by(SourceSyncRun.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        target = None
        if target_run_id is not None:
            target = await session.scalar(
                select(SourceSyncRun)
                .where(
                    SourceSyncRun.id == target_run_id,
                    SourceSyncRun.tenant_id == tenant,
                    SourceSyncRun.mapping_id == mapping_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if target is None:
                raise _conflict("SOURCE_UNAVAILABLE")
        run_id = None
        if action == "pause":
            if mapping.status != "active" or not current.enabled:
                raise _conflict()
            mapping.status, current.enabled = "paused", False
            disposition = "paused"
        elif action == "resume":
            if (
                mapping.status not in {"paused", "reconnect_required"}
                or current.enabled
                or request_policy is None
            ):
                raise _conflict()
            mapping.status, current.enabled = "active", True
            current.next_run_at = next_occurrence(request_policy.schedule, now)
            disposition = "active"
        elif action == "cancel":
            if target is None or target.status not in ACTIVE_RUNS or target.cancel_requested_at is not None:
                raise _conflict()
            run_id = target.id
            disposition = "reconciling" if target.status == "reconciling" else "stopping"
        elif action == "retire":
            mapping.status, current.enabled, current.next_run_at = "retired", False, None
            disposition = "retired"
        else:
            if mapping.status != "active" or not current.enabled or runs:
                raise _conflict()
            if action == "retry":
                if target is None or target.status not in RETRYABLE_RUNS:
                    raise _conflict()
                unknown = await session.scalar(
                    select(SourceSyncWork.id)
                    .join(SourceImportAttempt, SourceImportAttempt.id == SourceSyncWork.attempt_id)
                    .join(BulkItem, BulkItem.id == SourceImportAttempt.intake_item_id)
                    .where(
                        SourceSyncWork.tenant_id == tenant,
                        SourceSyncWork.mapping_id == mapping_id,
                        BulkItem.status.in_(("running", "reconciling", "queued")),
                        SourceImportAttempt.receipt_json.is_(None),
                    )
                    .limit(1)
                )
                if unknown is not None:
                    raise _conflict()
            run_id, job_id = str(uuid4()), str(uuid4())
            if _occurrence is not None and (request_policy is None or request_policy.schedule.kind == "manual"):
                raise _conflict()
            session.add(
                Job(
                    id=job_id,
                    tenant_id=tenant,
                    resource_id=mapping.id,
                    kind="content.source.reconcile",
                    idempotency_key="source:" + request.operation_id,
                    payload_hash=digest,
                    payload={"run_id": run_id, "mapping_id": mapping_id},
                    available_at=now,
                )
            )
            await session.flush()
            session.add(
                SourceSyncRun(
                    id=run_id,
                    tenant_id=tenant,
                    mapping_id=mapping_id,
                    policy_id=policy.id,
                    mapping_revision=mapping.revision,
                    connection_revision=connection.revision,
                    job_id=job_id,
                    trigger_kind=request_policy.schedule.kind if _occurrence is not None and request_policy else "retry" if action == "retry" else "manual",
                    operation_id=request.operation_id,
                    payload_sha256=digest,
                    occurrence_key=policy.id + ":" + _occurrence.isoformat() if _occurrence is not None else None,
                    status="queued",
                    page_sequence=0,
                    cursor_ciphertext=None,
                    scan_generation=current.scan_generation + 1,
                    enumeration_complete=False,
                    counters_json={},
                    finished_at=None,
                    retry_of_run_id=target_run_id if action == "retry" else None,
                )
            )
            await session.flush()
            disposition = "queued"
            current.scan_generation += 1
            current.scan_max_items, current.scan_observed_count = None, 0
            if _occurrence is not None and request_policy is not None:
                current.next_run_at = advance_occurrence(request_policy.schedule, _occurrence, now)
        current.revision += 1
        current.updated_at, mapping.updated_at = now, now
        result = SourceControlOutput(
            operation_id=request.operation_id,
            receipt_id=str(uuid4()),
            action=action,
            control_revision=current.revision,
            run_id=run_id,
            disposition=disposition,
        )
        session.add(
            SourceControlOperation(
                id=result.receipt_id,
                tenant_id=tenant,
                owner=owner,
                operation_id=request.operation_id,
                action=action,
                mapping_id=mapping_id,
                target_run_id=target_run_id,
                expected_revision=request.expected_revision,
                result_revision=current.revision,
                payload_sha256=digest,
                result_json=result.model_dump(mode="json"),
                created_at=now,
            )
        )
        await session.flush()
        # The marker's FK/trigger requires its immutable receipt to exist first.
        for run in [target] if action == "cancel" else runs if action == "retire" else []:
            if run is not None and run.cancel_requested_at is None:
                run.cancel_requested_at, run.cancel_operation_id = now, result.receipt_id
                run.updated_at = now
        await session.flush()
        return result
