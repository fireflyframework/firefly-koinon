# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""An admitted original alone never proves that a failed processing attempt may repeat."""

from datetime import UTC, datetime

from flycanon.core.services.sources.lineage.dtos import DocumentScope
from flycanon.core.services.sources.lineage.ports import LineageQuery, LineageRecord, LineageUnit

from koinon.knowledge.bulk.queue import BulkLease
from koinon.knowledge.bulk.recovery_intent import NativeFailureProof


def _utc(value: object) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def failed_native_proof(
    unit: LineageUnit,
    scope: DocumentScope,
    version: LineageRecord,
    lease: BulkLease,
    *,
    published: bool = False,
) -> NativeFailureProof | None:
    if published:
        return None
    head = await unit.first(LineageQuery("head", scope, source_id=version["source_id"]))
    if head is None or (head["version_id"], head["extraction_id"]) != (
        version["predecessor_id"],
        version["expected_extraction_id"],
    ):
        return None
    events = await unit.all(
        LineageQuery(
            "event",
            scope,
            source_id=version["source_id"],
            equal={"version_id": version["id"]},
            order=("-created_at", "-id"),
            limit=2,
        )
    )
    if not events or (
        events[0]["status"] != "failed"
        or events[0]["extraction_id"] is not None
        or events[0]["version_id"] != version["id"]
    ):
        return None
    event = events[0]
    failed_at = _utc(event["created_at"])
    if failed_at is None or len(events) > 1 and _utc(events[1]["created_at"]) == failed_at:
        return None
    started_at = _utc(lease.attempt_started_at)
    if started_at is not None and failed_at >= started_at:
        return NativeFailureProof(
            version_id=version["id"],
            event_id=event["id"],
            failed_at=failed_at,
            attempt=lease.attempt,
            attempt_started_at=started_at,
        )
    previous = lease.recovery_failure
    if previous is None or lease.expires_at is None or lease.attempt != previous.attempt + 1:
        return None
    proof = NativeFailureProof(
        version_id=version["id"],
        event_id=event["id"],
        failed_at=failed_at,
        attempt=previous.attempt,
        attempt_started_at=previous.attempt_started_at,
    )
    return proof if proof == previous else None
