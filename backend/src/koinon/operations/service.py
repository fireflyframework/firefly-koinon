# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded observations of resources owned by the native application context."""

import asyncio
import importlib
import os
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from pyfly.container import Container, Qualifier, service
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.relational.health import SqlAlchemyHealthIndicator
from pyfly.data.transaction import infrastructure_unit
from pyfly.observability.metrics import MetricsRegistry
from sqlalchemy import select, text

from koinon.catalog.entities import CatalogEntry
from koinon.catalog.service import CatalogService
from koinon.operations.settings import OperationalSettings


def observation(configured: bool, available: bool | None, reason: str, **fields) -> dict:
    return {
        **fields,
        "configured": configured,
        "available": available,
        "status": "unknown" if available is None else "passed" if available else "failed",
        "observed_at": datetime.now(UTC).isoformat(),
        "reason": reason,
    }


def storage_roundtrip(root: str) -> bool:
    path = None
    try:
        if not Path(root).is_dir():
            return False
        with tempfile.NamedTemporaryFile(prefix=".koinon-probe-", dir=root, delete=False) as handle:
            path = Path(handle.name)
            expected = os.urandom(32)
            handle.write(expected)
            handle.flush()
            os.fsync(handle.fileno())
        return path.read_bytes() == expected
    except OSError:
        return False
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


@service(name="operations.service")
class OperationsService:
    def __init__(
        self,
        catalog: CatalogService,
        config: Config,
        container: Container,
        datasource_registry: DataSourceRegistry,
        db_health_indicator: Annotated[SqlAlchemyHealthIndicator, Qualifier("db_health_indicator")],
        settings: OperationalSettings,
        metrics: MetricsRegistry | None = None,
    ):
        self.catalog, self.config, self.container = catalog, config, container
        self.sources, self.health, self.settings, self.metrics = (
            datasource_registry,
            db_health_indicator,
            settings,
            metrics,
        )
        self._storage_checks: dict[str, tuple[float, asyncio.Task]] = {}

    async def describe(self, subject: str, tenant_id: str) -> dict:
        await self.catalog.authorize(subject, tenant_id, "providers:write")
        health = await self.health.health()
        details = health.details.get("datasources", {})
        sources = []
        for source in self.sources.datasources():
            status = (
                details.get(source.qualified_name, {}).get("status", "UNKNOWN") if details else health.status
            )
            available = True if status == "UP" else None if status == "UNKNOWN" else False
            item = observation(
                True,
                available,
                {
                    True: "Native database probe succeeded",
                    False: "Native database probe failed",
                    None: "Native database probe could not verify this datasource",
                }[available],
                id=source.name,
                kind="database",
                driver=source.engine.dialect.name,
                pool=asdict(source.properties.pool),
            )
            item["role_policy"] = (
                await self._role_policy(source)
                if available
                else observation(
                    True, None, "Role policy was not checked while the datasource was unavailable"
                )
            )
            pool = source.engine.pool
            item["pool_usage"] = {
                key: getattr(pool, method)()
                for key, method in (
                    ("size", "size"),
                    ("checked_out", "checkedout"),
                    ("overflow", "overflow"),
                )
                if callable(getattr(pool, method, None))
            }
            if "overflow" in item["pool_usage"]:
                item["pool_usage"]["overflow"] = max(0, item["pool_usage"]["overflow"])
            sources.append(item)
        storage = await asyncio.gather(*(self._storage(domain) for domain in ("documents", "structured")))
        return {
            "ownership": "deployment",
            "read_only": True,
            "datasources": sources,
            "storage": storage,
            "indexes": await self._bounded_indexes(subject, tenant_id),
            "metrics": observation(
                self.metrics is not None,
                None,
                "Native metrics registration does not verify external collection",
                exporter_configured=bool(self.config.get("pyfly.observability.metrics.otlp.endpoint")),
                names=[
                    "pyfly_db_pool_size",
                    "pyfly_db_pool_checked_out",
                    "pyfly_db_pool_acquire_seconds",
                    "pyfly_db_query_duration_seconds",
                    "pyfly_db_queries_total",
                ],
            ),
            "limits": asdict(self.settings),
        }

    async def _role_policy(self, source) -> dict:
        if source.engine.dialect.name != "postgresql":
            return observation(True, None, "PostgreSQL runtime role policy requires PostgreSQL")
        try:
            async with asyncio.timeout(2), infrastructure_unit(source, read_only=True) as session:
                row = (
                    await session.execute(
                        text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
                    )
                ).one()
            privileged = source.name in {"canon_admin", "structured_admin"}
            valid = not row.rolsuper and (privileged or not row.rolbypassrls)
            return observation(
                True,
                valid,
                "Control role checked" if privileged else "Runtime role must not bypass row security",
                superuser=bool(row.rolsuper),
                bypass_rls=bool(row.rolbypassrls),
            )
        except Exception:
            return observation(True, None, "Role policy could not be verified")

    def _domain_settings(self, domain):
        module, kind = (
            ("flycanon.config", "CanonSettings")
            if domain == "documents"
            else ("flyquery.config", "FlyquerySettings")
        )
        try:
            cls = getattr(importlib.import_module(module), kind)
        except ImportError:
            return None
        return self.container.resolve(cls) if self.container.contains_type(cls) else None

    async def _storage(self, domain: str) -> dict:
        settings = self._domain_settings(domain)
        if settings is None:
            return observation(
                False, None, "Knowledge module storage is not bound in this context", id=domain
            )
        backend = settings.object_store_backend if domain == "documents" else settings.object_store
        fields = {"id": domain, "backend": backend, "ownership": "deployment", "read_only": True}
        if domain == "documents":
            fields["store_originals"] = settings.store_originals
        if backend not in {"local", "localfs"}:
            return observation(
                True, None, "Cloud storage is configured; no external probe was performed", **fields
            )
        root = settings.object_store_localfs_root if domain == "documents" else settings.object_store_base
        root = str(Path(root).absolute())
        cached = self._storage_checks.get(root)
        if cached is None or (cached[1].done() and time.monotonic() - cached[0] > 20):
            if sum(not task.done() for _, task in self._storage_checks.values()) >= 2:
                return observation(True, None, "Storage probe capacity is busy", **fields)
            task = asyncio.create_task(asyncio.to_thread(storage_roundtrip, root))
            task.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
            self._storage_checks[root] = (time.monotonic(), task)
        else:
            task = cached[1]
        done, _ = await asyncio.wait({task}, timeout=2)
        if not done:
            return observation(True, None, "Storage probe has not completed within its deadline", **fields)
        try:
            available = task.result()
        except Exception:
            available = False
        return observation(
            True,
            available,
            "Local object write/read/delete probe succeeded"
            if available
            else "Local object storage probe failed",
            **fields,
        )

    async def _bounded_indexes(self, subject, tenant_id):
        try:
            async with asyncio.timeout(5):
                return await self._indexes(subject, tenant_id)
        except TimeoutError:
            return [observation(True, None, "Index verification deadline reached", id="document-vectors")]

    async def _indexes(self, subject, tenant_id) -> list[dict]:
        if "canon" not in self.sources.names():
            return [
                observation(
                    False, None, "Document vector datasource is not configured", id="document-vectors"
                )
            ]
        source = self.sources.get("canon")
        if source.engine.dialect.name != "postgresql":
            return [
                observation(
                    True, None, "Vector index verification requires PostgreSQL", id="document-vectors"
                )
            ]
        from flycanon.models.entities.embedding_set import ann_cast, index_name_for

        from koinon.knowledge.adapters import native_scope
        from koinon.knowledge.entities import DomainBinding

        try:
            async with (
                asyncio.timeout(2),
                infrastructure_unit(self.sources.primary, read_only=True) as session,
            ):
                rows = (
                    await session.execute(
                        select(DomainBinding.workspace_id, DomainBinding.native_workspace_id)
                        .join(CatalogEntry, CatalogEntry.id == DomainBinding.catalog_id)
                        .where(
                            DomainBinding.tenant_id == tenant_id,
                            DomainBinding.domain == "canon",
                            CatalogEntry.status != "archived",
                        )
                        .distinct()
                        .limit(self.settings.max_index_workspaces + 1)
                    )
                ).all()
            if len(rows) > self.settings.max_index_workspaces:
                return [
                    observation(True, None, "Workspace verification limit reached", id="document-vectors")
                ]
            result = []
            for workspace, native_id in rows:
                await self.catalog.authorize(subject, tenant_id, "providers:write", workspace)
                with native_scope("canon", tenant_id, native_id, subject):
                    async with asyncio.timeout(2), infrastructure_unit(source, read_only=True) as session:
                        extension = bool(
                            (
                                await session.execute(
                                    text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")
                                )
                            ).scalar_one()
                        )
                        sets = (
                            await session.execute(
                                text(
                                    "SELECT id, dimensions, status, chunk_count, vector_count, index_name "
                                    "FROM canon_embedding_sets "
                                    "WHERE tenant_id=:tenant AND workspace_id=:workspace LIMIT 101"
                                ),
                                {"tenant": tenant_id, "workspace": native_id},
                            )
                        ).all()
                        indexes = 0
                        for embedding in sets[:100]:
                            cast, _ = ann_cast(embedding.dimensions)
                            if (
                                await session.execute(
                                    text(
                                        "SELECT EXISTS(SELECT 1 FROM pg_index i "
                                        "JOIN pg_class c ON c.oid=i.indexrelid "
                                        "JOIN pg_am a ON a.oid=c.relam WHERE c.oid=to_regclass(:name) "
                                        "AND i.indrelid=to_regclass('canon_chunk_vectors') "
                                        "AND i.indisvalid AND i.indisready AND a.amname='hnsw' "
                                        "AND position(quote_literal(:set_id) IN "
                                        "pg_get_expr(i.indpred,i.indrelid)) > 0 "
                                        "AND position(:cast IN pg_get_indexdef(i.indexrelid)) > 0)"
                                    ),
                                    {
                                        "name": embedding.index_name or index_name_for(embedding.id),
                                        "set_id": embedding.id,
                                        "cast": f"{cast}({embedding.dimensions})",
                                    },
                                )
                            ).scalar_one():
                                indexes += 1
                complete = (
                    bool(sets)
                    and len(sets) <= 100
                    and extension
                    and indexes == len(sets)
                    and all(
                        row.status in {"ready", "active", "retired"} and row.chunk_count == row.vector_count
                        for row in sets
                    )
                )
                result.append(
                    observation(
                        True,
                        complete if sets and len(sets) <= 100 else None,
                        "Scoped vector extension and physical HNSW indexes checked"
                        if complete
                        else "Scoped vector prerequisites are incomplete or unverified",
                        id="document-vectors",
                        workspace_id=workspace,
                        vector_extension=extension,
                        embedding_sets=len(sets),
                        physical_indexes=indexes,
                    )
                )
            return result or [
                observation(True, None, "No active document workspace is bound", id="document-vectors")
            ]
        except Exception:
            return [
                observation(
                    True, None, "Scoped vector prerequisites could not be verified", id="document-vectors"
                )
            ]
