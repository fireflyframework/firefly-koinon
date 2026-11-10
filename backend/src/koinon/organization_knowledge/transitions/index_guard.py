# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable parent authority for index work between mode worker leases."""

from typing import NoReturn

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException

from koinon.jobs.repository import JobRepository
from koinon.knowledge.indexes.ports import IndexParentAuthority
from koinon.organization_knowledge.service import OrganizationKnowledgeService
from koinon.organization_knowledge.transitions.index_attempts import ModeIndexAttemptRepository
from koinon.organization_knowledge.transitions.queue import original_actor
from koinon.organization_knowledge.transitions.repositories import (
    ModeTargetRepository,
    ModeTransitionRepository,
)


@service(name="organization_knowledge.mode_index_guard")
class ModeIndexGuard(IndexParentAuthority):
    def __init__(
        self,
        settings: OrganizationKnowledgeService,
        records: ModeTransitionRepository,
        targets: ModeTargetRepository,
        jobs: JobRepository,
        attempts: ModeIndexAttemptRepository | None = None,
    ):
        self.settings, self.records, self.targets, self.jobs = settings, records, targets, jobs
        self.attempts = attempts

    async def check(self, parent_id, tenant_id, index_record=None):
        unit = current_unit_of_work("primary")
        if unit is None or unit.completed or unit.read_only or not unit.read_from_primary:
            raise RuntimeError("Index parent validation requires a current primary write unit")
        await self.settings.catalog._lock_tenant(tenant_id)
        row = await self.records.find_by_id(parent_id, lock=LockMode.PESSIMISTIC_READ)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.active_slot != tenant_id
            or row.status not in {"queued", "running"}
            or row.stage not in {"prepare_indexes", "verify", "activate"}
            or row.requested_settings["documents"]["answer_mode"] != "rag"
        ):
            self.unavailable()
        jobs = await self.jobs.find_all(tenant_id=tenant_id, id=row.job_id, kind="knowledge.mode")
        if not jobs or jobs[0].status not in {"queued", "running"}:
            self.unavailable()
        with original_actor(row):
            await self.settings.catalog.authorize(row.actor, tenant_id, "settings:write")
            snapshot = await self.settings.snapshot(row.actor, tenant_id)
        if (snapshot.revision, snapshot.digest) != (row.base_revision, row.base_digest):
            self.unavailable()
        if index_record is not None:
            activation = index_record.transition or {}
            borrowed = activation.get("parent_mode_transition_id") == parent_id
            actor = activation.get("activation_actor") if borrowed else index_record.updated_by
            token = activation.get("activation_token_id") if borrowed else index_record.access_token_id
            if (
                index_record.tenant_id != tenant_id
                or index_record.domain != "documents"
                or actor != row.actor
                or token != row.access_token_id
            ):
                self.unavailable()
            targets = await self.targets.page(
                tenant_id,
                parent_id,
                kind="workspace",
                workspace_id=index_record.workspace_id,
                limit=1,
            )
            if not targets or targets[0].native_workspace_id != index_record.native_workspace_id:
                self.unavailable()

    async def admitted(self, parent_id, tenant_id, index_record):
        await self.check(parent_id, tenant_id, index_record)
        if self.attempts is None:
            self.unavailable()
        return await self.attempts.capture(tenant_id, parent_id, index_record)

    async def resolved(self, parent_id, tenant_id, index_record, outcome):
        if self.attempts is None or not index_record.transition.get("mode_activation_attempt_id"):
            self.unavailable()
        await self.attempts.resolve(
            tenant_id,
            parent_id,
            index_record.transition["mode_activation_attempt_id"],
            index_record,
            outcome,
            expected_revision=1,
        )

    @staticmethod
    def unavailable() -> NoReturn:
        raise ConflictException(
            "The linked mode preparation no longer authorizes this index work",
            code="INDEX_MODE_PREPARATION_INACTIVE",
        )
