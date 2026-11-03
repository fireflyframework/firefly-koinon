# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist one metadata page or coalesced journal scope per worker lease."""

from copy import deepcopy
from hashlib import sha256
from time import monotonic

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException

from koinon.organization_knowledge.transitions.progress import ModeProgress
from koinon.organization_knowledge.transitions.queue import ModeTransitionQueue, original_actor
from koinon.organization_knowledge.transitions.readiness_fence import (
    ModeReadinessFence,
    ModeReadinessSnapshot,
)
from koinon.organization_knowledge.transitions.verification import (
    ModeVerification,
    WorkspacePreparationRequired,
)


@service(name="organization_knowledge.mode_verification_progress")
class ModeVerificationProgress:
    def __init__(
        self,
        queue: ModeTransitionQueue,
        checker: ModeVerification,
        fence: ModeReadinessFence,
        progress: ModeProgress,
    ):
        self.queue, self.checker, self.fence, self.progress = queue, checker, fence, progress

    @staticmethod
    def catchup(baseline, watermark):
        return {
            "phase": "primary",
            "watermark": watermark.encode(),
            "primary_cursor": [baseline.primary, None],
            "canon_cursor": [baseline.canon, None],
        }

    async def restart(self, tenant_id, identifier, worker_id):
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        before = ModeReadinessSnapshot.decode(row.cursor.get("verified_generations"))
        current = await self.fence.snapshot(tenant_id)
        await self.restart_record(tenant_id, identifier, worker_id, before, self.catchup(before, current))

    @transactional
    async def restart_record(self, tenant_id, identifier, worker_id, before, state):
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if row.stage != "activate" or row.cursor.get("verified_generations") != before.encode():
            raise ConflictException("Verification progress changed", code="KNOWLEDGE_MODE_CHANGED")
        row.stage = "verify"
        row.cursor = {key: value for key, value in row.cursor.items() if key != "verified_generations"}
        row.cursor = {**row.cursor, "verification": state, "progress_reason": "knowledge_changed"}
        row.counters = {
            **row.counters,
            "verification_commit_conflicts": row.counters.get("verification_commit_conflicts", 0) + 1,
        }
        await self.queue.transitions.records.save(row)
        await self.progress.record(tenant_id, identifier, worker_id, stage="verify", milliseconds=0)

    async def step(self, tenant_id, identifier, worker_id):
        started = monotonic()
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if row.stage != "verify":
            raise ConflictException("Verification is no longer current", code="KNOWLEDGE_MODE_CHANGED")
        before = deepcopy(row.cursor.get("verification"))
        state = deepcopy(before)
        counts, complete = {}, False
        if state is None:
            baseline = await self.fence.snapshot(tenant_id)
            state = {"phase": "scan", "baseline": baseline.encode(), "after": None}
        elif state["phase"] == "scan":
            page = await self.check_page(row, worker_id, before, state, after=state["after"])
            if page is None:
                return
            counts = page.counts
            counts["verification_catalog_scanned"] = page.scanned
            state["after"] = page.after
            if page.complete:
                state = self.catchup(
                    ModeReadinessSnapshot.decode(state["baseline"]), await self.fence.snapshot(tenant_id)
                )
        elif state["phase"] in {"primary", "canon"}:
            domain = state["phase"]
            scope = state.get("scope")
            if scope is None:
                generation, workspace = state[domain + "_cursor"]
                changes = await self.fence.changes(
                    tenant_id, domain, after_generation=generation, after_workspace_id=workspace
                )
                if changes and changes[0].generation <= state["watermark"][domain]:
                    scope = {
                        "generation": changes[0].generation,
                        "workspace": changes[0].workspace_id,
                        "after": None,
                    }
                    state["scope"] = scope
                    counts["verification_dirty_scopes"] = 1
                else:
                    state["phase"] = "canon" if domain == "primary" else "children"
            if scope is not None:
                workspace = scope["workspace"] or None
                page = await self.check_page(
                    row,
                    worker_id,
                    before,
                    state,
                    after=scope["after"],
                    workspace_id=workspace if domain == "primary" else None,
                    native_workspace_id=workspace if domain == "canon" else None,
                )
                if page is None:
                    return
                counts.update(page.counts)
                counts["verification_catalog_scanned"] = page.scanned
                scope["after"] = page.after
                if page.complete:
                    state[domain + "_cursor"] = [scope["generation"], scope["workspace"]]
                    state.pop("scope")
        elif state["phase"] == "children":
            page = await self.children(tenant_id, identifier, worker_id, before, state.get("children_after"))
            if page is None:
                return
            state["children_after"], scanned = page
            counts["verification_indexes_scanned"] = scanned
            if scanned < 100:
                state["phase"] = "settle"
        elif state["phase"] == "settle":
            watermark = ModeReadinessSnapshot.decode(state["watermark"])
            current = await self.fence.snapshot(tenant_id)
            if current == watermark:
                complete = True
            else:
                state = self.catchup(watermark, current)
                counts["verification_change_rounds"] = 1
        else:
            raise ConflictException(
                "Verification has no supported checkpoint", code="KNOWLEDGE_MODE_VERIFICATION_REQUIRED"
            )
        await self.record(
            tenant_id,
            identifier,
            worker_id,
            before,
            state,
            counts,
            complete=complete,
            milliseconds=int(1000 * (monotonic() - started)),
        )

    @transactional
    async def children(self, tenant_id, identifier, worker_id, before, after):
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if row.stage != "verify" or row.cursor.get("verification") != before:
            raise ConflictException("Verification progress changed", code="KNOWLEDGE_MODE_CHANGED")
        indexes = await self.queue.transitions.indexes.mode_children(
            tenant_id, identifier, after_id=after, limit=100
        )
        pending = next(
            (
                index
                for index in indexes
                if index.status in {"activating", "queued", "building", "awaiting_index"}
            ),
            None,
        )
        if pending is not None:
            target_id = sha256(f"{identifier}\x1fworkspace\x1f{pending.workspace_id}".encode()).hexdigest()
            await self.progress.reject(
                tenant_id,
                identifier,
                worker_id,
                target_id=target_id,
                code="MODE_INDEX_RECOVERY_REQUIRED"
                if pending.status == "activating"
                else "INDEX_PREPARATION_REVIEW_REQUIRED",
                milliseconds=0,
                result={"index_id": pending.id, "job_id": pending.job_id},
            )
            return None
        return indexes[-1].id if indexes else after, len(indexes)

    async def check_page(self, row, worker_id, before, state, **scope):
        try:
            with original_actor(row):
                return await self.checker.page(row, page_size=100, **scope)
        except WorkspacePreparationRequired as error:
            if error.repairable:
                await self.prepare_scope(row.tenant_id, row.id, worker_id, before, state, error.workspace_id)
            elif error.target_id:
                await self.progress.reject(
                    row.tenant_id,
                    row.id,
                    worker_id,
                    target_id=error.target_id,
                    code=error.code,
                    milliseconds=0,
                )
            else:
                raise
            return None

    @transactional
    async def prepare_scope(self, tenant_id, identifier, worker_id, before, state, workspace_id):
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if row.stage != "verify" or row.cursor.get("verification") != before:
            raise ConflictException("Verification progress changed", code="KNOWLEDGE_MODE_CHANGED")
        cursor = {
            key: value
            for key, value in row.cursor.items()
            if key
            not in {
                "catalog_after",
                "preflight_after",
                "views_after",
                "indexes_after",
                "verified_generations",
                "discovery_cycle",
                "catalog_complete",
                "retire_after",
            }
        }
        cursor.update(
            verification=state, preparation_workspace=workspace_id, progress_reason="knowledge_changed"
        )
        row.counters = {
            **row.counters,
            "verification_workspace_repreparations": row.counters.get(
                "verification_workspace_repreparations", 0
            )
            + 1,
        }
        await self.queue.transitions.records.save(row)
        await self.progress.record(
            tenant_id,
            identifier,
            worker_id,
            stage="verify",
            next_stage="discovery",
            cursor=cursor,
            milliseconds=0,
        )

    @transactional
    async def record(
        self, tenant_id, identifier, worker_id, before, state, counts, *, complete, milliseconds
    ):
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if row.stage != "verify" or row.cursor.get("verification") != before:
            raise ConflictException("Verification progress changed", code="KNOWLEDGE_MODE_CHANGED")
        row.counters = {
            **row.counters,
            **{key: row.counters.get(key, 0) + value for key, value in counts.items()},
        }
        cursor = {**row.cursor, "verification": state}
        if counts.get("verification_change_rounds"):
            cursor["progress_reason"] = "knowledge_changed"
        if complete:
            cursor["verified_generations"] = state["watermark"]
        await self.queue.transitions.records.save(row)
        await self.progress.record(
            tenant_id,
            identifier,
            worker_id,
            stage="verify",
            cursor=cursor,
            next_stage="activate" if complete else None,
            milliseconds=milliseconds,
        )
