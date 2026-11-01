# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Existing native scoped adapters supply bounded read-only metadata, without provider calls."""

from uuid import UUID

from pyfly.container import Provider, component
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate
from sqlalchemy import text

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.indexes.adapters import NativeIndexAdapter, index_id
from koinon.platform.repositories import IndexTarget, PlatformRepository, StatusWindow


@component(name="platform.native_observations")
class PlatformNativeObservations:
    def __init__(
        self,
        records: PlatformRepository,
        indexes: Provider[NativeIndexAdapter | None],
        sources: DataSourceRegistry,
    ):
        self.records, self.index_adapter, self.sources = records, indexes, sources

    async def ingestion(self, subject: str, tenant_id: str, domain: str) -> StatusWindow:
        if domain not in {"documents", "structured"}:
            raise ValueError("Select one knowledge domain")
        native = "canon" if domain == "documents" else "structured"
        workspaces = await self.records.workspaces(tenant_id, native)
        if len(workspaces) > 32:
            return StatusWindow((), False)
        source = self.sources.get(native + "_admin")
        table = "canon_ingest_jobs" if domain == "documents" else "flyquery_ingest_jobs"
        schema = "public" if source.engine.dialect.name == "postgresql" else "main"
        states = []
        for _, workspace in workspaces:
            with native_scope(native, tenant_id, workspace, subject):
                async with TransactionTemplate(
                    native + "_admin",
                    propagation=Propagation.REQUIRES_NEW,
                    read_only=True,
                    read_from_primary=True,
                    isolation=Isolation.SERIALIZABLE,
                ).transaction() as unit:
                    if unit is None:
                        raise ValueError("A native metadata snapshot is required")
                    rows = (
                        (
                            await unit.resource.execute(
                                text(
                                    "SELECT status FROM "
                                    + schema
                                    + "."
                                    + table
                                    + " WHERE tenant_id=:tenant AND workspace_id=:workspace"
                                    + " ORDER BY id LIMIT :limit"
                                ),
                                {
                                    "tenant": tenant_id,
                                    "workspace": workspace if native == "canon" else UUID(workspace),
                                    "limit": 1001 - len(states),
                                },
                            )
                        )
                        .scalars()
                        .all()
                    )
                    states.extend(rows)
            if len(states) > 1000:
                return StatusWindow(tuple(states[:1000]), False)
        return StatusWindow(tuple(states), True)

    async def indexes(self, subject: str, tenant_id: str, targets: tuple[IndexTarget, ...]) -> bool:
        adapter = self.index_adapter.get()
        if adapter is None:
            raise ValueError("Native index observations are not configured")
        workspaces: dict[tuple[str, str], list[IndexTarget]] = {}
        for target in targets:
            workspaces.setdefault((target.domain, target.workspace_id), []).append(target)
        for candidates in workspaces.values():
            serving = [target for target in candidates if target.status == "active"]
            if len(serving) != 1:
                return False
            target = serving[0]
            native = "canon" if target.domain == "documents" else "structured"
            async with TransactionTemplate(
                native,
                propagation=Propagation.REQUIRES_NEW,
                read_only=True,
                read_from_primary=True,
                isolation=Isolation.SERIALIZABLE,
            ).transaction():
                value = await adapter.get_native(
                    tenant_id=tenant_id,
                    native_workspace_id=target.native_workspace_id,
                    catalog_workspace_id=target.workspace_id,
                    domain=target.domain,
                    actor=subject,
                    identifier=index_id(tenant_id, target.workspace_id, target.domain, target.native_id),
                )
                if (
                    not value
                    or value.get("status") != "active"
                    or value.get("active") is not True
                    or value.get("indexed") is not True
                ):
                    return False
                chunks, vectors = value.get("chunk_count"), value.get("vector_count")
                if (
                    type(chunks) is not int
                    or type(vectors) is not int
                    or chunks < 0
                    or chunks != vectors
                    or value.get("dimensions") != target.dimensions
                ):
                    return False
        return bool(targets)
