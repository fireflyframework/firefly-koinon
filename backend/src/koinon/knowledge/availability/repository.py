# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded primary projections; editable metadata never establishes serving readiness."""

import json
from datetime import UTC

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, or_, select

from koinon.catalog.entities import AuditEvent, CatalogEntry
from koinon.jobs.entities import Job
from koinon.knowledge.bulk.entities import BulkBatch, BulkItem
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.indexes.entities import KnowledgeIndex

ATTEMPT_KEY = "_koinon_processing"


def recorded_attempt(tenant_id):
    return (
        select(AuditEvent.id)
        .where(
            AuditEvent.tenant_id == tenant_id,
            AuditEvent.resource_id == CatalogEntry.id,
            AuditEvent.action == "knowledge.content.recorded",
            AuditEvent.details["operation"].as_string()
            == CatalogEntry.metadata_json[ATTEMPT_KEY]["operation"].as_string(),
            AuditEvent.details["state"].as_string()
            == CatalogEntry.metadata_json[ATTEMPT_KEY]["state"].as_string(),
        )
        .exists()
    )


async def mark_content_attempt(records, version: CatalogEntry, operation: str, state="unknown") -> None:
    if operation not in {"document.replace", "document.reingest", "table.reupload", "table.reingest"}:
        raise ValueError("Unknown content operation")
    if state not in {"unknown", "complete", "failed"}:
        raise ValueError("Unknown content outcome")
    version.metadata_json = {**version.metadata_json, ATTEMPT_KEY: {"operation": operation, "state": state}}
    await records.save(version)


@repository(name="knowledge.availability_records")
class AvailabilityRepository(Repository[CatalogEntry, str]):
    async def load(self, tenant_id: str, entries: list[CatalogEntry]) -> dict:
        session = self._require_session()
        ids = [entry.id for entry in entries]
        parents = list({entry.parent_id for entry in entries if entry.parent_id} | set(ids))
        bindings = (
            await session.scalars(
                select(DomainBinding).where(
                    DomainBinding.tenant_id == tenant_id,
                    DomainBinding.catalog_id.in_(ids + [entry.workspace_id for entry in entries]),
                )
            )
        ).all()
        by_id = {row.catalog_id: row for row in bindings if row.catalog_id in ids}
        workspaces = {(row.catalog_id, row.domain): row for row in bindings if row.entity_kind == "workspace"}
        attempts = (
            select(
                CatalogEntry.id,
                CatalogEntry.parent_id,
                CatalogEntry.status,
                CatalogEntry.metadata_json[ATTEMPT_KEY].label("marker"),
                func.row_number()
                .over(
                    partition_by=CatalogEntry.parent_id,
                    order_by=(CatalogEntry.created_at.desc(), CatalogEntry.id.desc()),
                )
                .label("n"),
            )
            .where(
                CatalogEntry.tenant_id == tenant_id,
                CatalogEntry.parent_id.in_(parents),
                CatalogEntry.kind == "index_version",
                recorded_attempt(tenant_id),
                CatalogEntry.metadata_json[ATTEMPT_KEY]["operation"]
                .as_string()
                .in_(("document.replace", "document.reingest", "table.reupload", "table.reingest")),
            )
            .subquery()
        )
        latest = {
            row.parent_id: row
            for row in (await session.execute(select(attempts).where(attempts.c.n == 1))).mappings()
        }
        bulk = (
            await session.execute(
                select(BulkItem, Job)
                .join(BulkBatch, BulkBatch.id == BulkItem.batch_id)
                .outerjoin(Job, Job.id == BulkItem.job_id)
                .where(
                    BulkBatch.tenant_id == tenant_id,
                    or_(BulkItem.asset_id.in_(ids), BulkItem.source_id.in_(ids)),
                )
            )
        ).all()
        queue = {
            identifier: (item, job) for item, job in bulk for identifier in (item.asset_id, item.source_id)
        }
        now = await session.scalar(select(func.current_timestamp()))
        if now is None:
            raise RuntimeError("The primary database clock is unavailable")
        now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
        index_jobs = (
            await session.execute(
                select(KnowledgeIndex, Job)
                .join(Job, Job.id == KnowledgeIndex.job_id)
                .where(
                    KnowledgeIndex.tenant_id == tenant_id,
                    Job.tenant_id == tenant_id,
                    KnowledgeIndex.workspace_id.in_([entry.workspace_id for entry in entries]),
                    KnowledgeIndex.status.in_(("queued", "building", "awaiting_index")),
                    Job.kind == "knowledge.index",
                    Job.status.in_(("queued", "running")),
                )
            )
        ).all()
        result = {}
        for entry in entries:
            binding = by_id.get(entry.id)
            if binding:
                workspace = (
                    workspaces.get((entry.workspace_id, binding.domain)) if entry.workspace_id else None
                )
                if (
                    binding.entity_kind != entry.kind
                    or binding.workspace_id != entry.workspace_id
                    or workspace is None
                    or binding.native_workspace_id != workspace.native_id
                ):
                    binding = None
            attempt = latest.get(entry.parent_id) or latest.get(entry.id)
            marker = attempt.marker if attempt else None
            if isinstance(marker, str):
                marker = json.loads(marker)
            latest_attempt = (
                {
                    "id": attempt.id,
                    "operation": marker["operation"],
                    "state": marker.get("state", "unknown"),
                }
                if attempt and marker
                else None
            )
            phase = "unknown"
            item, job = queue.get(entry.id, (None, None))
            if item is not None:
                phase = {
                    "failed": "failed",
                    "cancelled": "cancelled",
                    "reconciling": "reconciliation_required",
                    "succeeded": "complete",
                }.get(item.status, "unknown")
                if (
                    job
                    and job.tenant_id == tenant_id
                    and job.kind == "knowledge.bulk.intake"
                    and job.resource_id == item.asset_id
                ):
                    if item.status == "queued" and job.status == "queued":
                        phase = "queued"
                    if item.status == "running" and job.status == "running" and job.lease_until:
                        lease = job.lease_until
                        if (lease.replace(tzinfo=UTC) if lease.tzinfo is None else lease) > now:
                            phase = "processing"
            value = {
                "id": entry.id,
                "kind": entry.kind,
                "phase": phase,
                "latest_attempt": latest_attempt,
                "domain": binding.domain if binding else None,
                "native_id": binding.native_id if binding else None,
                "native_workspace_id": binding.native_workspace_id if binding else None,
                "index_phase": "unknown",
                "blocked": entry.status != "ready" or bool(entry.metadata_json.get("_koinon_intake")),
            }
            for index, index_job in index_jobs:
                domain = "documents" if value["domain"] == "canon" else "structured"
                if index.workspace_id == entry.workspace_id and index.domain == domain:
                    if index_job.status == "queued":
                        value["index_phase"] = "queued"
                    elif index_job.lease_until:
                        lease = index_job.lease_until
                        if (lease.replace(tzinfo=UTC) if lease.tzinfo is None else lease) > now:
                            value["index_phase"] = "indexing"
            value["stamp"] = json.dumps(
                [
                    entry.updated_at.isoformat(),
                    entry.parent_id,
                    entry.status,
                    binding.details_json if binding else None,
                    value,
                    job.updated_at.isoformat() if job else None,
                ],
                sort_keys=True,
            )
            result[entry.id] = value
        return result

    async def processing(self, tenant_id, workspace_id, page, size):
        from sqlalchemy import literal, union_all

        entry = CatalogEntry
        attempts = select(
            entry.id,
            entry.parent_id.label("resource_id"),
            entry.metadata_json[ATTEMPT_KEY]["operation"].as_string().label("operation"),
            entry.metadata_json[ATTEMPT_KEY]["state"].as_string().label("status"),
            entry.updated_at,
            literal(None).label("lease_until"),
        ).where(
            entry.tenant_id == tenant_id,
            entry.kind == "index_version",
            recorded_attempt(tenant_id),
            entry.metadata_json[ATTEMPT_KEY]["operation"]
            .as_string()
            .in_(("document.replace", "document.reingest", "table.reupload", "table.reingest")),
        )
        jobs = (
            select(
                Job.id,
                Job.resource_id,
                Job.kind.label("operation"),
                Job.status,
                Job.updated_at,
                Job.lease_until,
            )
            .join(entry, entry.id == Job.resource_id)
            .where(
                Job.tenant_id == tenant_id,
                entry.tenant_id == tenant_id,
                Job.kind.in_(("knowledge.index", "knowledge.bulk.intake", "knowledge.bulk.query")),
            )
        )
        if workspace_id:
            attempts = attempts.where(entry.workspace_id == workspace_id)
            jobs = jobs.where(entry.workspace_id == workspace_id)
        combined = union_all(attempts, jobs).subquery()
        return list(
            (
                await self._require_session().execute(
                    select(combined)
                    .order_by(combined.c.updated_at.desc(), combined.c.id.desc())
                    .offset((page - 1) * size)
                    .limit(size + 1)
                )
            ).mappings()
        )
