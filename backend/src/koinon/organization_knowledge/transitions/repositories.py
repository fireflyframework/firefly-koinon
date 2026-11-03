# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, select, union_all
from sqlalchemy.orm import aliased

from koinon.jobs.entities import Job
from koinon.knowledge.indexes.entities import KnowledgeIndex
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository
from koinon.organization_knowledge.transitions.entities import (
    KnowledgeModeIndexAttempt,
    KnowledgeModeIndexResolution,
    KnowledgeModeTarget,
    KnowledgeModeTransition,
)


@repository(name="organization_knowledge.mode_transitions")
class ModeTransitionRepository(Repository[KnowledgeModeTransition, str]):
    async def active(self, tenant_id):
        return await self._require_session().scalar(
            select(KnowledgeModeTransition)
            .where(KnowledgeModeTransition.active_slot == tenant_id)
            .execution_options(populate_existing=True)
        )

    @staticmethod
    def pending_recovery_query(tenant_id, parent_id=None):
        attempt, resolution = KnowledgeModeIndexAttempt, KnowledgeModeIndexResolution
        receipts = (
            select(attempt.id)
            .join(resolution, resolution.id == attempt.id)
            .where(
                attempt.tenant_id == tenant_id,
                resolution.tenant_id == tenant_id,
                resolution.status == "pending",
            )
        )
        indexed_receipt = (
            select(attempt.id)
            .join(resolution, resolution.id == attempt.id)
            .where(
                attempt.tenant_id == tenant_id,
                resolution.tenant_id == tenant_id,
                attempt.transition_id == KnowledgeModeTransition.id,
                attempt.index_id == KnowledgeIndex.id,
                resolution.status == "pending",
            )
            .exists()
        )
        legacy = (
            select(KnowledgeIndex.id)
            .select_from(KnowledgeModeTransition)
            .join(
                KnowledgeIndex,
                KnowledgeIndex.tenant_id == KnowledgeModeTransition.tenant_id,
            )
            .outerjoin(Job, KnowledgeIndex.job_id == Job.id)
            .where(
                KnowledgeModeTransition.tenant_id == tenant_id,
                *KnowledgeIndexRepository.mode_scope(tenant_id, KnowledgeModeTransition.id, "activating"),
                ~indexed_receipt,
            )
        )
        if parent_id is not None:
            receipts = receipts.where(attempt.transition_id == parent_id)
            legacy = legacy.where(KnowledgeModeTransition.id == parent_id)
        return union_all(receipts, legacy)

    async def has_pending_index_recovery(self, tenant_id):
        return (
            await self._require_session().scalar(self.pending_recovery_query(tenant_id).limit(1))
        ) is not None

    async def pending_recovery_count(self, tenant_id, parent_id):
        return int(
            await self._require_session().scalar(
                select(func.count()).select_from(self.pending_recovery_query(tenant_id, parent_id).subquery())
            )
            or 0
        )

    async def cancelled_jobs(self):
        return list(
            await self._require_session().scalars(
                select(KnowledgeModeTransition)
                .join(Job, KnowledgeModeTransition.job_id == Job.id)
                .where(
                    Job.tenant_id == KnowledgeModeTransition.tenant_id,
                    Job.kind == "knowledge.mode",
                    Job.status == "cancelled",
                    KnowledgeModeTransition.status.in_(("queued", "running", "failed")),
                )
                .order_by(KnowledgeModeTransition.id)
                .limit(25)
                .execution_options(populate_existing=True)
            )
        )

    async def cancelled_children(self):
        child = aliased(Job)
        pending = (
            select(child.id)
            .where(
                child.tenant_id == KnowledgeModeTransition.tenant_id,
                child.kind == "knowledge.index",
                child.status.in_(("queued", "running")),
                child.payload["parent_mode_transition_id"].as_string() == KnowledgeModeTransition.id,
            )
            .exists()
        )
        return list(
            await self._require_session().scalars(
                select(KnowledgeModeTransition)
                .where(KnowledgeModeTransition.status == "cancelled", pending)
                .order_by(KnowledgeModeTransition.id)
                .limit(25)
            )
        )

    async def latest(self, tenant_id):
        return await self._require_session().scalar(
            select(KnowledgeModeTransition)
            .where(KnowledgeModeTransition.tenant_id == tenant_id)
            .order_by(KnowledgeModeTransition.created_at.desc(), KnowledgeModeTransition.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )


@repository(name="organization_knowledge.mode_targets")
class ModeTargetRepository(Repository[KnowledgeModeTarget, str]):
    async def selected(self, tenant_id, transition_id, identifiers):
        identifiers = tuple(dict.fromkeys(identifiers))
        if len(identifiers) > 100:
            raise ValueError("Verification requires a bounded target page")
        if not identifiers:
            return {}
        row = KnowledgeModeTarget
        values = await self._require_session().scalars(
            select(row)
            .where(row.tenant_id == tenant_id, row.transition_id == transition_id, row.id.in_(identifiers))
            .execution_options(populate_existing=True)
        )
        return {value.id: value for value in values}

    async def observe(self, values):
        if not values:
            return {}
        if len(values) > 100:
            raise ValueError("Preparation writes require a bounded discovery page")
        tenant_id, transition_id = values[0].tenant_id, values[0].transition_id
        if any((value.tenant_id, value.transition_id) != (tenant_id, transition_id) for value in values):
            raise ValueError("Discovery writes require one exact transition scope")
        existing = await self.selected(tenant_id, transition_id, [value.id for value in values])
        deltas, changed = {}, []
        identity = ("catalog_id", "workspace_id", "native_id", "native_workspace_id", "kind")
        for value in values:
            previous = existing.get(value.id)
            if previous is None:
                changed.append(value)
                deltas["queued"] = deltas.get("queued", 0) + 1
            elif any(getattr(previous, name) != getattr(value, name) for name in identity):
                deltas[previous.status] = deltas.get(previous.status, 0) - 1
                deltas["queued"] = deltas.get("queued", 0) + 1
                previous.result = (
                    {"index_generation": previous.result.get("index_generation", 0) + 1}
                    if previous.kind == "workspace"
                    else {}
                )
                for name in identity:
                    setattr(previous, name, getattr(value, name))
                previous.status, previous.error_code, previous.snapshot = "queued", None, value.snapshot
                changed.append(previous)
            else:
                if previous.status == "excluded":
                    deltas["excluded"] = deltas.get("excluded", 0) - 1
                    deltas["queued"] = deltas.get("queued", 0) + 1
                    previous.status, previous.error_code = "queued", None
                    previous.result = {
                        key: item for key, item in previous.result.items() if key not in {"message", "action"}
                    }
                previous.snapshot = value.snapshot
                changed.append(previous)
        await self.save_all(changed)
        return deltas

    async def page(
        self,
        tenant_id,
        transition_id,
        *,
        after=None,
        status=None,
        kind=None,
        workspace_id=None,
        limit=100,
        active_only=False,
    ):
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("Preparation pages require a size from 1 to 200")
        query = select(KnowledgeModeTarget).where(
            KnowledgeModeTarget.tenant_id == tenant_id,
            KnowledgeModeTarget.transition_id == transition_id,
        )
        if kind is not None:
            if kind not in {"workspace", "document", "curated"}:
                raise ValueError("Select a preparation target kind")
            query = query.where(KnowledgeModeTarget.kind == kind)
        if workspace_id is not None:
            query = query.where(KnowledgeModeTarget.workspace_id == workspace_id)
        if after is not None:
            query = query.where(KnowledgeModeTarget.id > after)
        if status is not None:
            query = query.where(KnowledgeModeTarget.status == status)
        if active_only:
            query = query.where(KnowledgeModeTarget.status != "excluded")
        return list(
            await self._require_session().scalars(
                query.order_by(KnowledgeModeTarget.id).limit(limit).execution_options(populate_existing=True)
            )
        )

    async def counts(self, tenant_id, transition_id):
        return dict(
            (
                await self._require_session().execute(
                    select(KnowledgeModeTarget.status, func.count())
                    .where(
                        KnowledgeModeTarget.tenant_id == tenant_id,
                        KnowledgeModeTarget.transition_id == transition_id,
                    )
                    .group_by(KnowledgeModeTarget.status)
                )
            ).all()
        )

    async def mode_index_states(self, tenant_id, transition_id, identifiers):
        identifiers = tuple(dict.fromkeys(identifiers))
        if len(identifiers) > 200:
            raise ValueError("Index receipt lookup requires a bounded target page")
        if not identifiers:
            return {}
        rows = await self._require_session().scalars(
            select(KnowledgeIndex)
            .outerjoin(Job, KnowledgeIndex.job_id == Job.id)
            .where(
                *KnowledgeIndexRepository.mode_scope(tenant_id, transition_id),
                KnowledgeIndex.id.in_(identifiers),
            )
            .execution_options(populate_existing=True)
        )
        return {row.id: row for row in rows}
