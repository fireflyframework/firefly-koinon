# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


async def test_receive_uses_server_reserved_file_identity(monkeypatch):
    from flyquery.core.services.ingestion.stages import receive

    records = SimpleNamespace(insert_received=AsyncMock())
    monkeypatch.setattr(receive, "FileRepository", lambda _: records)
    store = SimpleNamespace(put=AsyncMock())
    reserved = uuid4()
    result = await receive.run_receive(
        tenant_id="north",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        filename="facts.csv",
        file_bytes=b"a,b\n1,2\n",
        actor="owner",
        object_store=store,
        session_factory=object(),
        settings=SimpleNamespace(max_file_mb=1, max_workspace_gb=1),
        workspace_storage_used_bytes=0,
        file_id=reserved,
    )
    try:
        assert result.file_id == reserved and records.insert_received.call_args.kwargs["file_id"] == reserved
        assert str(reserved) in store.put.call_args.args[0]
    finally:
        Path(result.local_temp_path).unlink()


@pytest.mark.parametrize("fails", [False, True])
async def test_durable_parse_reserves_all_tables_before_materialization_and_never_calls_naming_model(
    monkeypatch, tmp_path, fails
):
    from flyquery.core.services.ingestion.reader import ColumnSchema, MaterialiseResult, ProposedTable
    from flyquery.core.services.ingestion.stages import parse

    source = tmp_path / "facts.csv"
    source.write_bytes(b"raw original")
    reserved = uuid4()
    seen = []

    class Reader:
        async def enumerate_tables(self, *args):
            return [ProposedTable("facts", None, 1, 1)]

        async def materialise(self, source, table, target, **options):
            assert seen == ["reserved"]
            if fails:
                raise ValueError("materialization failed")
            Path(target).write_bytes(b"parquet")
            return MaterialiseResult(target, 7, 1, (ColumnSchema("column0", "INTEGER", False, 0),))

    async def reserve(tables):
        assert len(tables) == 1 and tables[0].name == "facts"
        seen.append("reserved")
        return (reserved,)

    async def inserted(**values):
        return values["table_id"]

    naming = AsyncMock(side_effect=AssertionError("Extract-only must never invoke authored naming"))
    monkeypatch.setattr(parse, "get_reader", lambda **values: Reader())
    monkeypatch.setattr(parse, "_next_version", AsyncMock(return_value=1))
    monkeypatch.setattr(parse, "_insert_table", inserted)
    monkeypatch.setattr(parse, "_propose_meaningful_column_names", naming)
    monkeypatch.setattr(parse.lineage, "emit", AsyncMock(return_value=None))
    args = dict(
        tenant_id="north",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        file_id=uuid4(),
        local_temp_path=str(source),
        file_format="csv",
        compression="none",
        object_store=SimpleNamespace(put=AsyncMock()),
        session_factory=object(),
        settings=SimpleNamespace(type_infer_sample_rows=10, max_title_rows=3),
        append_only=True,
        max_tables=16,
        extract_only=True,
        reserve_tables=reserve,
    )
    if fails:
        with pytest.raises(ValueError):
            await parse.run_parse(**args)
    else:
        result = await parse.run_parse(**args)
        try:
            assert result[0].table_id == reserved and result[0].result.columns[0].name == "column0"
        finally:
            for table in result:
                Path(table.local_parquet_path).unlink()
    naming.assert_not_awaited()
    assert source.read_bytes() == b"raw original"


async def test_extract_only_publish_does_not_trigger_implicit_enrichment_events(monkeypatch):
    from flyquery.core.services.ingestion.stages import publish

    session = SimpleNamespace(execute=AsyncMock())

    @asynccontextmanager
    async def unit(*args, **kwargs):
        yield session

    monkeypatch.setattr(publish, "infrastructure_unit", unit)
    monkeypatch.setattr(publish.lineage, "emit", AsyncMock())
    publisher = SimpleNamespace(publish_schema_updated=AsyncMock())
    await publish.run_publish(
        tenant_id="north",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        table_id=uuid4(),
        snapshot_id=uuid4(),
        n_columns=1,
        n_rows_actual=1,
        publisher=publisher,
        session_factory=object(),
        emit_event=False,
    )
    assert session.execute.await_count == 2
    publisher.publish_schema_updated.assert_not_awaited()
