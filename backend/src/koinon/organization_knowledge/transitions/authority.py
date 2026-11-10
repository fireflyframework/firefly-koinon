# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exact target authority and short primary-before-native publication units."""

from contextlib import asynccontextmanager

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException
from sqlalchemy import select

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.service import KnowledgeFacade
from koinon.organization_knowledge.transitions.queue import ModeTransitionQueue, original_actor
from koinon.organization_knowledge.transitions.repositories import ModeTargetRepository
from koinon.security.authority import primary_authority
from koinon.security.policy_reads import policy_read


@service(name="organization_knowledge.mode_target_authority")
class ModeTargetAuthority:
    def __init__(self, queue: ModeTransitionQueue, knowledge: KnowledgeFacade, targets: ModeTargetRepository):
        self.queue, self.knowledge, self.targets = queue, knowledge, targets

    async def target(self, tenant_id, identifier, target_id):
        rows = await self.targets.find_all(id=target_id, tenant_id=tenant_id, transition_id=identifier)
        if not rows:
            raise AccessDenied("Preparation target is unavailable", code="ACCESS_DENIED")
        return rows[0]

    async def check(self, tenant_id, identifier, worker_id, target_id):
        target = await self.target(tenant_id, identifier, target_id)
        transition = await self.queue.authorize(tenant_id, identifier, worker_id)
        with original_actor(transition):
            await self.knowledge.catalog._refresh_managed_memberships(transition.actor)
            async with policy_read():
                chain = await self.knowledge._read_chain(
                    transition.actor, tenant_id, target.catalog_id, "knowledge:search"
                )
                entry = chain[0]
                expected_kind = "knowledge_item" if target.kind == "curated" else target.kind
                if entry.kind != expected_kind or entry.workspace_id != target.workspace_id:
                    self.changed()
                if target.kind != "curated":
                    rows = await self.knowledge.bindings.find_all(
                        tenant_id=tenant_id, catalog_id=entry.id, domain="canon"
                    )
                    if not rows and target.kind == "workspace" and target.native_id is None:
                        return target
                    binding = await self.knowledge.binding(tenant_id, entry.id, "canon", entry=entry)
                    workspace = chain[-1]
                    workspace_binding = await self.knowledge.binding(
                        tenant_id, workspace.id, "canon", entry=workspace
                    )
                    if (
                        binding.native_id != target.native_id
                        or binding.native_workspace_id != target.native_workspace_id
                        or workspace_binding.native_id != target.native_workspace_id
                    ):
                        self.changed()
        return target

    @staticmethod
    def changed():
        raise ConflictException(
            "This source or its destination changed. Start preparation for the current Library.",
            code="KNOWLEDGE_MODE_SOURCE_CHANGED",
        )

    @asynccontextmanager
    async def publication(self, tenant_id, identifier, worker_id, target_id):
        if any(current_unit_of_work(name) is not None for name in ("primary", "canon", "structured")):
            raise RuntimeError("Mode publication must start outside existing database units")
        await self.target(tenant_id, identifier, target_id)
        transition = await self.queue.transitions.records.find_by_id(identifier)
        catalog = self.knowledge.catalog
        with original_actor(transition):
            await catalog._refresh_managed_memberships(transition.actor)
            async with primary_authority(read_only=False):
                await catalog._lock_tenant(tenant_id)
                await self.queue.authorize(tenant_id, identifier, worker_id)
                members = await catalog.membership_repository.find_all(
                    subject=transition.actor, tenant_id=tenant_id
                )
                for member in sorted(members, key=lambda value: value.id):
                    await catalog.membership_repository.find_by_id(member.id, lock=LockMode.PESSIMISTIC_READ)
                if transition.access_token_id:
                    if catalog.restriction is None:
                        raise AccessDenied("The submitting token is unavailable", code="ACCESS_DENIED")
                    await catalog.restriction.tokens.find_by_id(
                        transition.access_token_id, lock=LockMode.PESSIMISTIC_READ
                    )
                target = await self.target(tenant_id, identifier, target_id)
                chain = await self.knowledge._read_chain(
                    transition.actor, tenant_id, target.catalog_id, "knowledge:search"
                )
                for entry in sorted(chain, key=lambda value: value.id):
                    await catalog.catalog_repository.find_by_id(entry.id, lock=LockMode.PESSIMISTIC_READ)
                bindings = await self.knowledge.bindings._require_session().scalars(
                    select(DomainBinding)
                    .where(
                        DomainBinding.tenant_id == tenant_id,
                        DomainBinding.domain == "canon",
                        DomainBinding.catalog_id.in_({target.catalog_id, target.workspace_id}),
                    )
                    .order_by(DomainBinding.id)
                )
                for binding in bindings:
                    await self.knowledge.bindings.find_by_id(binding.id, lock=LockMode.PESSIMISTIC_READ)
                await self.check(tenant_id, identifier, worker_id, target_id)
                yield
