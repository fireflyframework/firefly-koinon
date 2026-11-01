# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from koinon.knowledge.availability.adapter import NativeAvailabilityAdapter


@pytest.fixture
async def native_session():
    from sqlalchemy.ext.asyncio import async_sessionmaker

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TABLE canon_sources (id TEXT, tenant_id TEXT, workspace_id TEXT, "
                "status TEXT, metadata_json JSON, n_chunks INT, updated_at TEXT)"
            )
        )
        await connection.execute(
            text(
                "CREATE TABLE canon_chunks (id TEXT, source_id TEXT,tenant_id TEXT, "
                "workspace_id TEXT,content TEXT)"
            )
        )
        for table, columns in (
            (
                "canon_source_heads",
                "source_id TEXT,tenant_id TEXT,workspace_id TEXT,version_id TEXT,extraction_id TEXT",
            ),
            ("canon_source_versions", "id TEXT,source_id TEXT,tenant_id TEXT,workspace_id TEXT"),
            (
                "canon_source_extractions",
                "id TEXT,source_id TEXT,tenant_id TEXT,workspace_id TEXT,version_id TEXT,coverage "
                "TEXT,purpose TEXT",
            ),
            (
                "canon_source_parts",
                "source_id TEXT,tenant_id TEXT,workspace_id TEXT,extraction_id TEXT,projection_chunk_id "
                "TEXT,text TEXT,kind TEXT",
            ),
        ):
            await connection.execute(text(f"CREATE TABLE {table} ({columns})"))
        for source, tenant, workspace, chunks in (
            ("source", "tenant", "workspace", 1),
            ("foreign", "other", "workspace", 1),
            ("empty", "tenant", "workspace", 0),
            ("forged", "tenant", "workspace", 1),
        ):
            await connection.execute(
                text(
                    "INSERT INTO canon_sources VALUES "
                    "(:id,:tenant,:workspace,'ingested',:metadata,:chunks,'v1')"
                ),
                {
                    "id": source,
                    "tenant": tenant,
                    "workspace": workspace,
                    "chunks": chunks,
                    "metadata": json.dumps({"_source_lineage": {"version_id": "v1", "extraction_id": "e1"}}),
                },
            )
            if source != "forged":
                params = {"id": source, "tenant": tenant, "workspace": workspace}
                await connection.execute(
                    text("INSERT INTO canon_source_heads VALUES (:id,:tenant,:workspace,'v1','e1')"), params
                )
                await connection.execute(
                    text("INSERT INTO canon_source_versions VALUES ('v1',:id,:tenant,:workspace)"), params
                )
                await connection.execute(
                    text(
                        "INSERT INTO canon_source_extractions VALUES "
                        "('e1',:id,:tenant,:workspace,'v1','file_section','ingestion')"
                    ),
                    params,
                )
                if chunks:
                    await connection.execute(
                        text(
                            "INSERT INTO canon_source_parts VALUES "
                            "(:id,:tenant,:workspace,'e1',:id,'actual','chunk')"
                        ),
                        params,
                    )
            if chunks:
                await connection.execute(
                    text("INSERT INTO canon_chunks VALUES (:id,:id,:tenant,:workspace,'actual')"),
                    {"id": source, "tenant": tenant, "workspace": workspace},
                )
    async with async_sessionmaker(engine)() as session:
        yield session
    await engine.dispose()


async def test_native_current_text_requires_positive_coverage_and_exact_scope(native_session):
    adapter = NativeAvailabilityAdapter(None)
    entries = [{"id": source, "native_id": source} for source in ("source", "foreign", "empty")]
    result = await adapter.documents(native_session, "tenant", "workspace", entries)
    assert set(result) == {"source", "empty"}
    assert result["source"]["read"]["state"] == "ready"
    assert result["source"]["search"]["state"] == "unknown"  # No qualified PostgreSQL ANN.
    assert result["empty"]["read"]["state"] == "unknown"
    assert result["empty"]["search"]["state"] == "unknown"
    assert not await adapter.documents(native_session, "tenant", "another", entries)


async def test_native_revision_and_coverage_change_are_observable(native_session):
    adapter = NativeAvailabilityAdapter(None)
    entries = [{"id": "document", "native_id": "source"}]
    first = await adapter.documents(native_session, "tenant", "workspace", entries)
    await native_session.execute(
        text("UPDATE canon_sources SET n_chunks=2,updated_at='v2' WHERE id='source'")
    )
    second = await adapter.documents(native_session, "tenant", "workspace", entries)
    assert first != second
    assert second["document"]["read"]["state"] == "unknown"


async def test_editable_native_metadata_without_immutable_current_head_is_not_ready(native_session):
    result = await NativeAvailabilityAdapter(None).documents(
        native_session, "tenant", "workspace", [{"id": "forged", "native_id": "forged"}]
    )
    assert result["forged"]["read"]["state"] == "unknown"
    assert result["forged"]["revision"]["source_version_id"] is None


async def test_native_observation_uses_primary_even_inside_lagging_replica_unit(native_session, tmp_path):
    import sqlite3

    from pyfly.context.application_context import ApplicationContext
    from pyfly.core.config import Config
    from pyfly.data.relational.auto_configuration import RelationalAutoConfiguration
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import TransactionTemplate

    connection = await native_session.connection()
    raw = await connection.get_raw_connection()
    script = "\n".join([line async for line in raw.driver_connection.iterdump()])
    primary = tmp_path / "native-primary.db"
    replica = tmp_path / "native-replica.db"
    for path in (primary, replica):
        with sqlite3.connect(path) as database:
            database.executescript(script)
            if path == replica:
                database.execute("DELETE FROM canon_source_heads")
    ctx = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'primary.db'}",
                            "datasources": {
                                "canon": {
                                    "url": f"sqlite+aiosqlite:///{primary}",
                                    "ddl-auto": "none",
                                    "read-replica": {"url": f"sqlite+aiosqlite:///{replica}"},
                                }
                            },
                        }
                    }
                }
            }
        )
    )
    ctx.register_bean(RelationalAutoConfiguration)
    await ctx.start()
    try:
        adapter = NativeAvailabilityAdapter(ctx.get_bean(DataSourceRegistry))
        selected = {
            "asset": {
                "id": "asset",
                "kind": "document",
                "domain": "canon",
                "native_id": "source",
                "native_workspace_id": "workspace",
            }
        }
        async with TransactionTemplate("canon", read_only=True).transaction() as replica_unit:
            assert await replica_unit.resource.scalar(text("SELECT count(*) FROM canon_source_heads")) == 0
            result = await adapter.observe("actor", "tenant", selected)
            assert result["asset"]["read"]["state"] == "ready"
            assert await replica_unit.resource.scalar(text("SELECT count(*) FROM canon_source_heads")) == 0
    finally:
        await ctx.stop()


def test_current_file_readiness_requires_current_positive_coverage_active_pointer_and_real_ann():
    from koinon.knowledge.availability.adapter import document_observation

    row = dict(
        id="source",
        version_id="v1",
        extraction_id="e1",
        status="ingested",
        n_chunks=2,
        actual_chunks=2,
        total_chunks=2,
        updated_at="v1",
        coverage="file_section",
    )
    active = {"id": "current"}
    ready = document_observation(row, active, 2, True)
    assert ready["read"]["reason"] == "CURRENT_TEXT_RECORDED"
    assert ready["search"]["state"] == "ready" and ready["revision"]["active_index_id"] == "current"
    for changed, pointer, vectors, ann in (
        ({}, None, 2, True),
        ({}, active, 2, False),
        ({}, active, 1, True),
        ({"n_chunks": 0, "actual_chunks": 0, "total_chunks": 0}, active, 0, True),
        ({"total_chunks": 3}, active, 2, True),
        ({"extraction_id": None}, active, 2, True),
    ):
        assert document_observation({**row, **changed}, pointer, vectors, ann)["search"]["state"] != "ready"


async def test_structured_current_snapshot_is_required_and_foreign_scope_is_not_observed():
    from sqlalchemy.ext.asyncio import async_sessionmaker

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        for table, columns in (
            ("flyquery_datasets", "id TEXT,tenant_id TEXT,workspace_id TEXT,status TEXT,updated_at TEXT"),
            (
                "flyquery_tables",
                "id TEXT,dataset_id TEXT,tenant_id TEXT,workspace_id TEXT,is_active BOOL,"
                "current_snapshot_id TEXT,updated_at TEXT",
            ),
            (
                "flyquery_schema_snapshots",
                "id TEXT,table_id TEXT,tenant_id TEXT,workspace_id TEXT,status TEXT,parquet_object_key TEXT",
            ),
        ):
            await connection.execute(text(f"CREATE TABLE {table} ({columns})"))
        await connection.execute(text("INSERT INTO flyquery_datasets VALUES ('d','t','w','ACTIVE','one')"))
        await connection.execute(
            text("INSERT INTO flyquery_tables VALUES ('tab','d','t','w',true,'s1','one')")
        )
        await connection.execute(
            text("INSERT INTO flyquery_schema_snapshots VALUES ('s1','tab','t','w','READY','object/s1')")
        )
        await connection.execute(
            text("INSERT INTO flyquery_schema_snapshots VALUES ('s2','tab','t','w','FAILED',NULL)")
        )
    selections = [
        {"id": "dataset", "kind": "dataset", "native_id": "d"},
        {"id": "table", "kind": "table", "native_id": "tab"},
    ]
    adapter = NativeAvailabilityAdapter(None)
    async with async_sessionmaker(engine)() as session:
        old = await adapter.structured(session, "t", "w", selections)
        assert old["table"]["revision"]["snapshot_id"] == "s1"
        assert all(value["query"]["state"] == "ready" for value in old.values())
        assert not await adapter.structured(session, "other", "w", selections)
        await session.execute(text("UPDATE flyquery_tables SET current_snapshot_id='s2'"))
        current = await adapter.structured(session, "t", "w", selections)
        assert current["table"]["revision"]["snapshot_id"] == "s2"
        assert all(value["query"]["state"] == "pending" for value in current.values())
        assert current != old
    await engine.dispose()
