# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable bounded progress and safe, actionable prerequisite receipts."""

from datetime import timedelta

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException

from koinon.catalog.errors import AccessDenied
from koinon.organization_knowledge.transitions.entities import now
from koinon.organization_knowledge.transitions.queue import ModeTransitionQueue
from koinon.organization_knowledge.transitions.repositories import ModeTargetRepository

_PREREQUISITES = {
    "INDEX_QUALIFICATION_OUTCOME_UNKNOWN": (
        "The prior embedding qualification has no committed index receipt. Inspect "
        "the provider outcome. "
        "Explicitly retrying preparation may repeat that provider call and its "
        "usage; the active mode is unchanged.",
        "inspect_index_job",
    ),
    "INDEX_PREPARATION_REVIEW_REQUIRED": (
        "The linked index job stopped or its coverage changed. Inspect that exact "
        "receipt, then explicitly retry "
        "preparation to resume the preserved target. Incomplete embedding calls may "
        "incur usage again; the active mode is unchanged.",
        "inspect_index_job",
    ),
    "MODE_INDEX_RECOVERY_REQUIRED": (
        "An index activation is not reconciled. Inspect its current native pointer "
        "and permitted finish or restore action. "
        "The active mode is unchanged.",
        "reconcile_index",
    ),
    "SOURCE_VERSION_PREPARATION_REQUIRED": (
        "This source has no committed document version. Open the document's reprocessing action, "
        "complete processing, then retry preparation. The active mode is unchanged.",
        "reprocess_document",
    ),
    "SOURCE_PROCESSING_REQUIRED": (
        "This document has not completed processing. Open its processing job before retrying. "
        "The active mode is unchanged.",
        "inspect_document_job",
    ),
    "KNOWLEDGE_RLM_UNQUALIFIED": (
        "RLM is not qualified for curated knowledge in this Library. Keep RAG for this corpus. "
        "The active mode is unchanged.",
        "keep_rag",
    ),
    "DOCUMENT_ORIGINAL_INTEGRITY_FAILED": (
        "This source's stored original does not match its recorded hash. Restore "
        "the exact original "
        "through the document recovery process before retrying. The active mode is unchanged.",
        "inspect_source_integrity",
    ),
    "DOCUMENT_VIEW_LIMIT": (
        "This source exceeds the configured recorded-view limit. Review the source size and "
        "supported processing limits. The active mode is unchanged.",
        "inspect_source_limits",
    ),
    "KNOWLEDGE_MODE_SOURCE_CHANGED": (
        "A source or destination changed during preparation. Start preparation for "
        "the current Library. "
        "The active mode is unchanged.",
        "restart_preparation",
    ),
    "DOCUMENT_VERSION_CONFLICT": (
        "This document changed while its recorded view was being prepared. Retry to "
        "verify its current "
        "committed version. The active mode is unchanged.",
        "retry_preparation",
    ),
}
_MODEL_CODES = frozenset(
    {
        "KNOWLEDGE_MODEL_BINDING_REQUIRED",
        "KNOWLEDGE_PROVIDER_UNAVAILABLE",
        "KNOWLEDGE_PROVIDER_CREDENTIAL_REQUIRED",
        "KNOWLEDGE_MODEL_OPTIONS_INVALID",
        "KNOWLEDGE_EMBEDDING_BINDING_REQUIRED",
    }
)


def prerequisite(code):
    if code in _MODEL_CODES:
        return (
            "Configure and enable the requested mode's selected model connection, then "
            "retry preparation. "
            "The active mode is unchanged.",
            "configure_models",
        )
    return _PREREQUISITES.get(
        code,
        (
            "Preparation stopped before activation. Inspect the linked source and job outcome before "
            "retrying; the active mode is unchanged.",
            "inspect_preparation",
        ),
    )


@service(name="organization_knowledge.mode_progress")
class ModeProgress:
    def __init__(self, queue: ModeTransitionQueue, targets: ModeTargetRepository):
        self.queue, self.targets = queue, targets

    async def target(self, tenant_id, identifier, target_id):
        rows = await self.targets.find_all(id=target_id, tenant_id=tenant_id, transition_id=identifier)
        if not rows:
            raise AccessDenied("Preparation target is unavailable", code="ACCESS_DENIED")
        return rows[0]

    @staticmethod
    def count_transition(row, before, after):
        if before == after:
            return
        counters = {
            **dict.fromkeys(("prepared", "ready", "waiting", "failed", "queued", "excluded"), 0),
            **row.counters,
        }
        counters[before] = max(0, counters.get(before, 0) - 1)
        counters[after] = counters.get(after, 0) + 1
        row.counters = counters

    @transactional
    async def record(
        self,
        tenant_id,
        identifier,
        worker_id,
        *,
        stage,
        milliseconds,
        target_id=None,
        status=None,
        result=None,
        next_stage=None,
        cursor=None,
        delay_seconds=0,
    ):
        if milliseconds < 0 or not 0 <= delay_seconds <= 60:
            raise ValueError("Preparation timing and scheduling must be bounded")
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if row.stage != stage:
            raise ConflictException("Preparation stage changed", code="KNOWLEDGE_MODE_CHANGED")
        if target_id is not None:
            target = await self.target(tenant_id, identifier, target_id)
            if status not in {"prepared", "ready", "waiting"}:
                raise ValueError("Select a preparation target state")
            self.count_transition(row, target.status, status)
            target.status, target.result, target.error_code = status, result or {}, None
            target.updated_at = now()
            await self.targets.save(target)
        row.stage_milliseconds = {
            **row.stage_milliseconds,
            stage: row.stage_milliseconds.get(stage, 0) + milliseconds,
        }
        if cursor is not None:
            row.cursor = cursor
        if next_stage is not None:
            if next_stage not in {
                "discovery",
                "preflight",
                "repair_views",
                "prepare_indexes",
                "verify",
                "activate",
            }:
                raise ValueError("Select a preparation stage")
            row.stage = next_stage
            if next_stage == "verify" and "preparation_workspace" in row.cursor:
                row.cursor = {
                    key: value for key, value in row.cursor.items() if key != "preparation_workspace"
                }
        _, job = await self.queue.fence(tenant_id, identifier, worker_id)
        row.status, row.updated_at = "queued", now()
        row.revision += 1
        job.status, job.worker_id, job.lease_until, job.attempts = "queued", None, None, 0
        job.available_at = now() + timedelta(seconds=delay_seconds)
        await self.queue.transitions.jobs.repository.save(job)
        await self.queue.transitions.records.save(row)

    @transactional
    async def reject(self, tenant_id, identifier, worker_id, *, target_id, code, milliseconds, result=None):
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        target = await self.target(tenant_id, identifier, target_id)
        code = (
            code if isinstance(code, str) and code.isupper() and len(code) <= 64 else "KNOWLEDGE_MODE_FAILED"
        )
        message, action = prerequisite(code)
        self.count_transition(row, target.status, "failed")
        target.status, target.error_code = "failed", code
        target.result = {
            **target.result,
            **(result or {}),
            "message": message,
            "action": action,
            "catalog_id": target.catalog_id,
        }
        target.updated_at = now()
        await self.targets.save(target)
        row.cursor = {**row.cursor, "error_target_id": target_id}
        row.stage_milliseconds = {
            **row.stage_milliseconds,
            row.stage: row.stage_milliseconds.get(row.stage, 0) + milliseconds,
        }
        await self.queue.fail(tenant_id, identifier, worker_id, code=code)
        row.error = message
        await self.queue.transitions.records.save(row)
