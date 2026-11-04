# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Paged canonical discovery; primary snapshots end before preparation work."""

from hashlib import sha256
from time import monotonic
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException
from sqlalchemy import select

from koinon.catalog.entities import CatalogEntry
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.service import KnowledgeFacade
from koinon.organization_knowledge.transitions.entities import KnowledgeModeTarget, now
from koinon.organization_knowledge.transitions.queue import ModeTransitionQueue, original_actor
from koinon.organization_knowledge.transitions.repositories import ModeTargetRepository
from koinon.security.policy_reads import policy_read


@service(name="organization_knowledge.mode_discovery")
class ModeDiscovery:
    def __init__(self, knowledge: KnowledgeFacade, targets: ModeTargetRepository, queue: ModeTransitionQueue):
        self.knowledge, self.targets, self.queue = knowledge, targets, queue

    async def step(self, tenant_id, identifier, worker_id, *, page_size=100):
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("Discovery pages require a size from 1 to 100")
        started = monotonic()
        transition = await self.queue.authorize(tenant_id, identifier, worker_id)
        if transition.cursor.get("catalog_complete"):
            return await self.retire(tenant_id, identifier, worker_id, page_size=page_size)
        before = transition.cursor.get("catalog_after")
        previous_cycle = transition.cursor.get("discovery_cycle")
        cycle = previous_cycle or uuid4().hex
        with original_actor(transition):
            entries, admitted = await self.page(
                transition,
                after=before,
                page_size=page_size,
                workspace_id=transition.cursor.get("preparation_workspace"),
            )
        complete = len(entries) < page_size
        await self.record(
            tenant_id,
            identifier,
            worker_id,
            before,
            previous_cycle,
            cycle,
            entries[-1].id if entries else before,
            admitted,
            complete=complete,
            scanned=len(entries),
            milliseconds=int(1000 * (monotonic() - started)),
        )
        return complete and not (
            transition.cursor.get("preparation_workspace") or transition.cursor.get("reconcile_targets")
        )

    async def page(
        self, transition, *, after=None, page_size=100, workspace_id=None, native_workspace_id=None
    ):
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("Discovery pages require a size from 1 to 100")
        tenant_id, identifier = transition.tenant_id, transition.id
        await self.knowledge.catalog._refresh_managed_memberships(transition.actor)
        async with policy_read():
            session = self.targets._require_session()
            query = select(CatalogEntry).where(
                CatalogEntry.tenant_id == tenant_id,
                CatalogEntry.kind.in_(("workspace", "document", "knowledge_item")),
                CatalogEntry.status != "archived",
            )
            if after is not None:
                query = query.where(CatalogEntry.id > after)
            if workspace_id is not None:
                query = query.where(CatalogEntry.workspace_id == workspace_id)
            if native_workspace_id is not None:
                query = query.where(
                    CatalogEntry.workspace_id.in_(
                        select(DomainBinding.catalog_id).where(
                            DomainBinding.tenant_id == tenant_id,
                            DomainBinding.domain == "canon",
                            DomainBinding.entity_kind == "workspace",
                            DomainBinding.native_workspace_id == native_workspace_id,
                            DomainBinding.native_id == native_workspace_id,
                        )
                    )
                )
            entries = list(await session.scalars(query.order_by(CatalogEntry.id).limit(page_size)))
            await self.knowledge.catalog._prefetch_ancestry(tenant_id, (entry.id for entry in entries))
            identifiers = {value for entry in entries for value in (entry.id, entry.workspace_id) if value}
            bindings = (
                {
                    value.catalog_id: value
                    for value in await session.scalars(
                        select(DomainBinding).where(
                            DomainBinding.tenant_id == tenant_id,
                            DomainBinding.domain == "canon",
                            DomainBinding.catalog_id.in_(identifiers),
                        )
                    )
                }
                if identifiers
                else {}
            )
            admitted = []
            for entry in entries:
                try:
                    await self.knowledge._read_chain(
                        transition.actor, tenant_id, entry.id, "knowledge:search"
                    )
                except AccessDenied as error:
                    if error.code == "RESOURCE_ARCHIVED":
                        continue
                    raise
                binding, workspace = bindings.get(entry.id), bindings.get(entry.workspace_id)
                if entry.kind != "knowledge_item":
                    if entry.kind == "document" and binding is None:
                        raise AccessDenied(
                            "A document has no admitted native binding", code="BINDING_UNAVAILABLE"
                        )
                    if binding is not None and (
                        binding.entity_kind != entry.kind
                        or binding.workspace_id != entry.workspace_id
                        or workspace is None
                        or workspace.entity_kind != "workspace"
                        or workspace.workspace_id != entry.workspace_id
                        or workspace.native_id != workspace.native_workspace_id
                        or binding.native_workspace_id != workspace.native_workspace_id
                    ):
                        raise AccessDenied(
                            "Native binding scope disagrees with catalog", code="BINDING_SCOPE_MISMATCH"
                        )
                admitted.append(
                    {
                        "id": sha256(f"{identifier}\x1f{entry.kind}\x1f{entry.id}".encode()).hexdigest(),
                        "tenant_id": tenant_id,
                        "transition_id": identifier,
                        "kind": "curated" if entry.kind == "knowledge_item" else entry.kind,
                        "catalog_id": entry.id,
                        "workspace_id": entry.workspace_id,
                        "native_workspace_id": binding.native_workspace_id if binding else None,
                        "native_id": binding.native_id if binding else None,
                        "snapshot": {"catalog_status": entry.status},
                    }
                )
        return entries, admitted

    @transactional
    async def record(
        self,
        tenant_id,
        identifier,
        worker_id,
        before,
        previous_cycle,
        cycle,
        after,
        targets,
        *,
        complete,
        scanned,
        milliseconds,
    ):
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if (
            row.cursor.get("catalog_after") != before
            or row.cursor.get("discovery_cycle") != previous_cycle
            or row.stage != "discovery"
        ):
            raise ConflictException("Discovery progress changed", code="KNOWLEDGE_MODE_CHANGED")
        deltas = await self.targets.observe(
            [
                KnowledgeModeTarget(**{**value, "snapshot": {**value["snapshot"], "discovery_cycle": cycle}})
                for value in targets
            ]
        )
        row.cursor = {**row.cursor, "catalog_after": after, "discovery_cycle": cycle}
        row.counters = {
            **row.counters,
            "catalog_scanned": row.counters.get("catalog_scanned", 0) + scanned,
            **{key: max(0, row.counters.get(key, 0) + value) for key, value in deltas.items()},
        }
        row.stage_milliseconds = {
            **row.stage_milliseconds,
            "discovery": row.stage_milliseconds.get("discovery", 0) + milliseconds,
        }
        if complete:
            if row.cursor.get("preparation_workspace") or row.cursor.get("reconcile_targets"):
                row.cursor = {**row.cursor, "catalog_complete": True}
            else:
                row.stage = "preflight"
        row.revision += 1
        row.updated_at = now()
        await self.queue.transitions.records.save(row)

    @transactional
    async def retire(self, tenant_id, identifier, worker_id, *, page_size=100):
        started = monotonic()
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if row.stage != "discovery" or not row.cursor.get("catalog_complete"):
            raise ConflictException("Discovery progress changed", code="KNOWLEDGE_MODE_CHANGED")
        targets = await self.targets.page(
            tenant_id,
            identifier,
            workspace_id=row.cursor.get("preparation_workspace"),
            after=row.cursor.get("retire_after"),
            limit=page_size,
        )
        counters, changed = dict(row.counters), []
        for target in targets:
            if (
                target.status != "excluded"
                and target.snapshot.get("discovery_cycle") != row.cursor["discovery_cycle"]
            ):
                counters[target.status] = max(0, counters.get(target.status, 0) - 1)
                counters["excluded"] = counters.get("excluded", 0) + 1
                target.status, target.error_code, target.updated_at = "excluded", None, now()
                target.result = {
                    **target.result,
                    "action": None,
                    "message": (
                        "This source or folder is no longer in the current Library scope. "
                        "Earlier preparation receipts are retained."
                    ),
                }
                changed.append(target)
        await self.targets.save_all(changed)
        row.stage_milliseconds = {
            **row.stage_milliseconds,
            "discovery": row.stage_milliseconds.get("discovery", 0) + int(1000 * (monotonic() - started)),
        }
        row.counters = {
            **counters,
            "discovery_targets_checked": counters.get("discovery_targets_checked", 0) + len(targets),
        }
        row.cursor = {
            **row.cursor,
            "retire_after": targets[-1].id if targets else row.cursor.get("retire_after"),
        }
        if len(targets) < page_size:
            row.stage = "preflight"
            row.cursor = {
                key: value
                for key, value in row.cursor.items()
                if key not in {"catalog_complete", "reconcile_targets"}
            }
        row.revision += 1
        row.updated_at = now()
        await self.queue.transitions.records.save(row)
        return len(targets) < page_size
