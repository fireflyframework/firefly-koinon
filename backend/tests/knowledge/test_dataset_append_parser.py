# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


async def test_append_name_collision_never_changes_existing_native_table(monkeypatch):
    from flyquery.core.services.ingestion.stages import parse
    from pyfly.kernel import ConflictException
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine)
    old, old_file, dataset, workspace = [uuid4() for _ in range(4)]
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TABLE flyquery_tables(id TEXT,tenant_id TEXT,workspace_id TEXT,"
                "dataset_id TEXT,source_file_id TEXT,name TEXT,qualified_name TEXT,sheet_or_json_path TEXT,"
                "kind TEXT,UNIQUE(dataset_id,name))"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO flyquery_tables VALUES(:id,'north',:workspace,:dataset,"
                ":file,'orders','sales.orders',NULL,'UPLOADED')"
            ),
            dict(id=str(old), workspace=str(workspace), dataset=str(dataset), file=str(old_file)),
        )

    @asynccontextmanager
    async def unit(*args, **kwargs):
        async with factory.begin() as session:

            class Parameters:
                async def execute(self, statement, values):
                    return await session.execute(
                        statement,
                        {
                            key: str(value) if hasattr(value, "hex") else value
                            for key, value in values.items()
                        },
                    )

            yield Parameters()

    monkeypatch.setattr(parse, "infrastructure_unit", unit)
    try:
        with pytest.raises(ConflictException) as error:
            await parse._insert_table(
                table_id=uuid4(),
                tenant_id="north",
                workspace_id=workspace,
                dataset_id=dataset,
                source_file_id=uuid4(),
                name="orders",
                qualified_name="sales.orders",
                sheet_or_json_path=None,
                session_factory=factory,
                append_only=True,
            )
        assert error.value.code == "DATASET_APPEND_TABLE_EXISTS"
        async with factory() as session:
            rows = (await session.execute(text("SELECT id,source_file_id FROM flyquery_tables"))).all()
        assert rows == [(str(old), str(old_file))]
    finally:
        await engine.dispose()


@pytest.mark.parametrize("table_limit", [1, 128])
async def test_append_parser_never_swallows_a_section_failure_or_exceeds_enumerated_bound(
    tmp_path, monkeypatch, table_limit
):
    from flyquery.config import FlyquerySettings
    from flyquery.core.services.ingestion.reader import ProposedTable
    from flyquery.core.services.ingestion.stages import parse
    from pyfly.kernel import PayloadTooLargeException

    source = tmp_path / "input.xlsx"
    source.write_bytes(b"controlled parser input")
    reader = SimpleNamespace(
        enumerate_tables=AsyncMock(return_value=[ProposedTable(name, name, 1, 1) for name in ("One", "Two")]),
        materialise=AsyncMock(side_effect=RuntimeError("worksheet failed")),
    )
    monkeypatch.setattr(parse, "get_reader", lambda **_: reader)
    monkeypatch.setattr(parse, "_next_version", AsyncMock(return_value=1))
    with pytest.raises(PayloadTooLargeException if table_limit == 1 else RuntimeError):
        await parse.run_parse(
            tenant_id="north",
            workspace_id=uuid4(),
            dataset_id=uuid4(),
            file_id=uuid4(),
            local_temp_path=str(source),
            file_format="xlsx",
            compression="none",
            object_store=object(),
            session_factory=lambda: None,
            settings=FlyquerySettings(),
            append_only=True,
            max_tables=table_limit,
        )
    assert reader.materialise.await_count == (0 if table_limit == 1 else 1)
