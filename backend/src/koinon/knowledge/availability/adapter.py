# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Primary native observations contain no provider calls or workspace-wide counts."""

import json
from collections import defaultdict

from pyfly.container import component
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.indexes.ann import ann_qualified


def capability(state, reason):
    return {"state": state, "reason": reason}


def statement(sql):
    return text(sql).bindparams(bindparam("ids", expanding=True))


def document_observation(row, active, vector_count, qualified):
    revision = {
        "source_version_id": row["version_id"],
        "extraction_id": row["extraction_id"],
        "active_index_id": active["id"] if active else None,
    }
    recorded = bool(revision["source_version_id"] and revision["extraction_id"])
    complete = (
        row["status"] == "ingested" and 0 < row["n_chunks"] == row["actual_chunks"] == row["total_chunks"]
    )
    searchable = bool(recorded and complete and active and qualified and vector_count == row["actual_chunks"])
    return {
        "stamp": json.dumps(
            [
                str(row["updated_at"]),
                row["status"],
                revision,
                row["actual_chunks"],
                row["n_chunks"],
                row["total_chunks"],
                row["coverage"],
                vector_count,
                qualified,
            ],
            sort_keys=True,
        ),
        "revision": revision,
        "phase": "failed"
        if row["status"] == "failed"
        else "complete"
        if recorded and complete
        else "unknown",
        "read": capability("ready", "CURRENT_TEXT_RECORDED")
        if recorded and complete
        else capability("unknown", "CURRENT_TEXT_NOT_VERIFIED"),
        "search": capability("ready", "ACTIVE_INDEX_QUALIFIED")
        if searchable
        else capability("pending", "ACTIVE_INDEX_INCOMPLETE")
        if recorded and complete and active
        else capability("unknown", "ACTIVE_INDEX_NOT_VERIFIED"),
        "query": capability("not_applicable", "DOCUMENT"),
    }


@component(name="knowledge.availability_native")
class NativeAvailabilityAdapter:
    def __init__(self, datasources: DataSourceRegistry):
        self.datasources = datasources

    async def observe(self, subject: str, tenant_id: str, selections: dict) -> dict:
        groups = defaultdict(list)
        for selection in selections.values():
            if selection["domain"] in {"canon", "structured"} and selection["native_id"]:
                groups[(selection["domain"], selection["native_workspace_id"])].append(selection)
        result = {}
        for (domain, workspace), entries in groups.items():
            try:
                source = self.datasources.get(domain)
                with native_scope(domain, tenant_id, workspace, subject):
                    async with TransactionTemplate(
                        source,
                        propagation=Propagation.REQUIRES_NEW,
                        isolation=Isolation.SERIALIZABLE,
                        read_only=True,
                        read_from_primary=True,
                    ).transaction() as unit:
                        if unit is None:
                            continue
                        session = unit.resource
                        rows = await (
                            self.documents(session, tenant_id, workspace, entries)
                            if domain == "canon"
                            else self.structured(session, tenant_id, workspace, entries)
                        )
                        result.update(rows)
            except (KeyError, SQLAlchemyError, ServiceUnavailableException):
                # No native data is preferable to an inferred successful ingestion.
                continue
        return result

    async def documents(self, session, tenant, workspace, entries):
        params = {"tenant": tenant, "workspace": workspace, "ids": [e["native_id"] for e in entries]}
        sources = (
            (
                await session.execute(
                    statement(
                        "SELECT s.id,s.status,s.n_chunks,s.updated_at,v.id AS version_id,e.id AS "
                        "extraction_id,"
                        "e.coverage,e.purpose,(SELECT count(*) FROM canon_chunks c WHERE "
                        "c.tenant_id=s.tenant_id "
                        "AND c.workspace_id=s.workspace_id AND c.source_id=s.id) AS total_chunks,"
                        "(SELECT count(*) FROM canon_chunks c JOIN canon_source_parts p "
                        "ON p.projection_chunk_id=c.id AND p.text=c.content AND p.kind='chunk' "
                        "AND p.tenant_id=c.tenant_id AND p.workspace_id=c.workspace_id AND "
                        "p.source_id=c.source_id "
                        "WHERE c.tenant_id=s.tenant_id AND c.workspace_id=s.workspace_id AND "
                        "c.source_id=s.id "
                        "AND p.extraction_id=e.id) AS actual_chunks FROM canon_sources s "
                        "LEFT JOIN canon_source_heads h ON h.source_id=s.id AND h.tenant_id=s.tenant_id "
                        "AND h.workspace_id=s.workspace_id LEFT JOIN canon_source_versions v "
                        "ON v.id=h.version_id AND v.source_id=s.id AND v.tenant_id=s.tenant_id "
                        "AND v.workspace_id=s.workspace_id LEFT JOIN canon_source_extractions e "
                        "ON e.id=h.extraction_id AND e.version_id=v.id AND e.source_id=s.id "
                        "AND e.tenant_id=s.tenant_id AND e.workspace_id=s.workspace_id AND "
                        "e.purpose='ingestion' "
                        "WHERE s.tenant_id=:tenant AND s.workspace_id=:workspace AND s.id IN :ids"
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        active = None
        vectors = {}
        qualified = False
        if session.get_bind().dialect.name == "postgresql":
            from pyfly.agentic.vectorstores.scoped import scope_namespace

            params["namespace"] = scope_namespace(tenant, workspace)
            await session.execute(text("SELECT set_config('app.scope_namespace',:namespace,true)"), params)
            active = (
                (
                    await session.execute(
                        text(
                            "SELECT s.id,s.dimensions FROM canon_workspaces w JOIN canon_embedding_sets s "
                            "ON s.id=w.active_embedding_set_id AND s.tenant_id=w.tenant_id AND "
                            "s.workspace_id=w.id "
                            "WHERE w.tenant_id=:tenant AND w.id=:workspace AND s.status='active'"
                        ),
                        params,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if active:
                params["set_id"] = active["id"]
                qualified = await ann_qualified(
                    session, domain="documents", set_id=active["id"], dimensions=active["dimensions"]
                )
                vectors = dict(
                    (
                        await session.execute(
                            statement(
                                "SELECT c.source_id,count(*) FROM canon_chunks c JOIN canon_chunk_vectors v "
                                "ON v.id=c.id AND v.text=c.content AND v.set_id=:set_id AND "
                                "v.namespace=:namespace "
                                "WHERE c.tenant_id=:tenant AND c.workspace_id=:workspace AND c.source_id "
                                "IN :ids "
                                "GROUP BY c.source_id"
                            ),
                            params,
                        )
                    ).all()
                )
        by_id = {
            row["id"]: document_observation(row, active, vectors.get(row["id"]), qualified) for row in sources
        }
        return {e["id"]: by_id[e["native_id"]] for e in entries if e["native_id"] in by_id}

    async def structured(self, session, tenant, workspace, entries):
        result = {}
        for kind in ("dataset", "table"):
            selected = [entry for entry in entries if entry["kind"] == kind]
            if not selected:
                continue
            params = {"tenant": tenant, "workspace": workspace, "ids": [e["native_id"] for e in selected]}
            if kind == "table":
                sql = (
                    "SELECT t.id,ss.id AS snapshot_id,ss.status,ss.parquet_object_key,t.updated_at,"
                    "d.status AS dataset_status,t.is_active FROM flyquery_tables t "
                    "JOIN flyquery_datasets d ON d.id=t.dataset_id AND d.tenant_id=t.tenant_id "
                    "AND d.workspace_id=t.workspace_id LEFT JOIN flyquery_schema_snapshots ss "
                    "ON ss.id=t.current_snapshot_id AND ss.table_id=t.id AND ss.tenant_id=t.tenant_id "
                    "AND ss.workspace_id=t.workspace_id WHERE t.tenant_id=:tenant "
                    "AND t.workspace_id=:workspace AND t.id IN :ids"
                )
                rows = (await session.execute(statement(sql), params)).mappings().all()
                by_id = {}
                for row in rows:
                    ready = bool(
                        row["is_active"]
                        and row["dataset_status"] == "ACTIVE"
                        and row["status"] == "READY"
                        and row["parquet_object_key"]
                    )
                    by_id[str(row["id"])] = self.structured_value(
                        ready,
                        {"snapshot_id": str(row["snapshot_id"]) if row["snapshot_id"] else None},
                        [
                            str(row["updated_at"]),
                            row["status"],
                            row["dataset_status"],
                            row["parquet_object_key"],
                        ],
                    )
            else:
                rows = (
                    (
                        await session.execute(
                            statement(
                                "SELECT d.id,d.status,d.updated_at,t.id AS table_id,t.current_snapshot_id,"
                                "ss.status AS snapshot_status,ss.parquet_object_key FROM flyquery_datasets d "
                                "LEFT JOIN flyquery_tables t ON t.dataset_id=d.id AND "
                                "t.tenant_id=d.tenant_id "
                                "AND t.workspace_id=d.workspace_id AND t.is_active=true "
                                "LEFT JOIN flyquery_schema_snapshots ss ON ss.id=t.current_snapshot_id "
                                "AND ss.table_id=t.id AND ss.tenant_id=t.tenant_id AND "
                                "ss.workspace_id=t.workspace_id "
                                "WHERE d.tenant_id=:tenant AND d.workspace_id=:workspace AND d.id IN :ids "
                                "ORDER BY t.id"
                            ),
                            params,
                        )
                    )
                    .mappings()
                    .all()
                )
                grouped = defaultdict(list)
                for row in rows:
                    grouped[str(row["id"])].append(row)
                by_id = {}
                for identifier, tables in grouped.items():
                    ready = bool(tables) and all(
                        t["status"] == "ACTIVE"
                        and t["table_id"]
                        and t["snapshot_status"] == "READY"
                        and t["parquet_object_key"]
                        for t in tables
                    )
                    by_id[identifier] = self.structured_value(
                        ready, {}, [[str(t[k]) for k in t] for t in tables]
                    )
            result.update({e["id"]: by_id[e["native_id"]] for e in selected if e["native_id"] in by_id})
        return result

    @staticmethod
    def structured_value(ready, revision, stamp):
        return {
            "stamp": json.dumps([revision, stamp], sort_keys=True),
            "revision": revision,
            "read": capability("ready", "CURRENT_SNAPSHOT_RECORDED")
            if ready
            else capability("unknown", "CURRENT_SNAPSHOT_NOT_VERIFIED"),
            "query": capability("ready", "CURRENT_SNAPSHOT_RECORDED")
            if ready
            else capability("pending", "CURRENT_SNAPSHOT_NOT_READY"),
            "search": capability("not_applicable", "STRUCTURED_DOMAIN"),
        }
