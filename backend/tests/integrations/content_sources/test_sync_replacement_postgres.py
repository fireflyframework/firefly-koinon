# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Replacement preparation cannot mutate a previously published native table."""

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_source_migration_postgres import load
from test_source_migration_postgres import source_database as source_database

schema = load("backend/tests/knowledge/test_metadata_provenance_schema.py")
metadata_database = schema.metadata_database
pytestmark = pytest.mark.integration


@pytest.mark.parametrize("prepared", [True, False])
async def test_parser_staging_preserves_published_file_and_initial_behavior(
    metadata_database, tmp_path, prepared
):
    from flyquery.core.services.ingestion.stages.parse import run_parse

    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        workspace, dataset, baseline = schema.replacement_dataset(connection)
    table_id = UUID(baseline["members"][0]["table_id"])
    source = tmp_path / "data.csv"
    source.write_text("amount\n10\n20\n")
    file_id = uuid4()
    with psycopg.connect(uri) as connection:
        connection.execute(
            "INSERT INTO flyquery_files(id,tenant_id,workspace_id,dataset_id,original_filename,"
            "file_format,size_bytes,content_hash_sha256,object_store_key,uploaded_by,status) "
            "VALUES(%s,'tenant',%s,%s,'data.csv','csv',13,%s,'prepared/key','reader','RECEIVED')",
            (file_id, workspace, dataset, "c" * 64),
        )

    class Files:
        async def put(self, key, body, content_type):
            path = tmp_path / "objects" / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)

    async def reserve(proposed):
        assert len(proposed) == 1
        return (table_id,)

    engine = create_async_engine(uri.replace("postgresql://", "postgresql+asyncpg://"))
    sessions = async_sessionmaker(engine)
    try:
        parsed = await run_parse(
            tenant_id="tenant",
            workspace_id=workspace,
            dataset_id=dataset,
            file_id=file_id,
            local_temp_path=str(source),
            file_format="csv",
            compression="none",
            object_store=Files(),
            session_factory=sessions,
            settings=SimpleNamespace(type_infer_sample_rows=10, max_title_rows=3),
            original_filename="data.csv",
            extract_only=True,
            reserve_tables=reserve,
            max_tables=16,
            _defer_table_bindings=prepared,
        )
        assert len(parsed) == 1 and parsed[0].table_id == table_id
        assert parsed[0].result.n_rows_actual == 2
        assert Path(parsed[0].local_parquet_path).is_file()
        async with sessions() as session:
            row = (
                await session.execute(
                    text("SELECT source_file_id,current_snapshot_id,name FROM flyquery_tables WHERE id=:id"),
                    {"id": table_id},
                )
            ).one()
        expected = UUID(baseline["native_file_id"]) if prepared else file_id
        assert row.source_file_id == expected
        assert str(row.current_snapshot_id) == baseline["members"][0]["snapshot_id"]
        assert row.name == "data"
        Path(parsed[0].local_parquet_path).unlink()
    finally:
        await engine.dispose()
