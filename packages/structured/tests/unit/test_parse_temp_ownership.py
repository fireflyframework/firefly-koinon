# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Only successfully returned parser outputs transfer to the caller."""

import asyncio
import os
import stat
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


class MemoryStore:
    def __init__(self):
        self.blobs = {"original": b"caller original"}

    async def put(self, key, body, content_type):
        self.blobs[key] = body


class TinyReader:
    formats = ("csv",)

    def __init__(self, scenario):
        self.scenario = scenario

    async def enumerate_tables(self, source_path, rules):
        from flyquery.core.services.ingestion.reader import ProposedTable

        count = 2 if self.scenario.startswith("later_") else 1
        return [ProposedTable(f"section_{i}", None, 1, 1) for i in range(count)]

    async def materialise(self, source, table, target, **options):
        from flyquery.core.services.ingestion.reader import ColumnSchema, MaterialiseResult

        Path(target).write_bytes(b"small local output")
        if self.scenario == "skip":
            raise ValueError("partial materialisation")
        if self.scenario == "cancel_materialise":
            raise asyncio.CancelledError
        return MaterialiseResult(target, 18, 1, (ColumnSchema("amount", "INTEGER", False, 0),))


@pytest.fixture
def allocated_outputs(monkeypatch, tmp_path):
    paths, descriptors = [], []
    mktemp, mkstemp = tempfile.mktemp, tempfile.mkstemp

    def name(*args, **kwargs):
        path = mktemp(*args, **{**kwargs, "dir": tmp_path})
        paths.append(Path(path))
        return path

    def reserve(*args, **kwargs):
        fd, path = mkstemp(*args, **{**kwargs, "dir": tmp_path})
        paths.append(Path(path))
        descriptors.append(fd)
        return fd, path

    monkeypatch.setattr(tempfile, "mktemp", name)
    monkeypatch.setattr(tempfile, "mkstemp", reserve)
    return paths, descriptors


@pytest.mark.parametrize(
    "scenario",
    [
        "success",
        "reservation",
        "skip",
        "cancel_materialise",
        "cancel_step",
        "begin_failure",
        "table_failure",
        "later_table_failure",
        "later_version_failure",
        "reupload_failure",
    ],
)
async def test_parse_transfers_only_returned_outputs(monkeypatch, tmp_path, allocated_outputs, scenario):
    from flyquery.core.services.ingestion.stages import parse

    paths, descriptors = allocated_outputs
    source = tmp_path / "user-original.csv"
    source.write_bytes(b"caller original")
    store = MemoryStore()
    monkeypatch.setattr(parse, "get_reader", lambda **kwargs: TinyReader(scenario))
    versions = 0

    async def next_version(*args):
        nonlocal versions
        versions += 1
        if scenario == "later_version_failure" and versions == 2:
            raise RuntimeError("version lookup")
        return 1

    monkeypatch.setattr(parse, "_next_version", next_version)
    inserted = 0

    async def insert(**kwargs):
        nonlocal inserted
        inserted += 1
        if scenario == "table_failure" or scenario == "later_table_failure" and inserted == 2:
            raise RuntimeError("table insert")
        return kwargs["table_id"]

    monkeypatch.setattr(parse, "_insert_table", insert)
    monkeypatch.setattr(parse, "_update_table_file", AsyncMock(side_effect=RuntimeError("file pointer")))

    async def propose(**kwargs):
        return kwargs["mat_result"]

    monkeypatch.setattr(parse, "_propose_meaningful_column_names", propose)

    async def emit(event, **values):
        if event == "begin_section":
            if scenario == "reservation":
                assert paths[-1].exists(), "parser output was not reserved before lineage awaited"
                assert stat.S_IMODE(paths[-1].stat().st_mode) == 0o600
                with pytest.raises(OSError):
                    os.fstat(descriptors[-1])
            if scenario == "begin_failure":
                raise RuntimeError("lineage begin")
        if event == "step" and values["kind"] == "materialize" and scenario == "cancel_step":
            raise asyncio.CancelledError
        return None

    monkeypatch.setattr(parse.lineage, "emit", emit)
    args = dict(
        tenant_id="owned",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        file_id=uuid4(),
        local_temp_path=str(source),
        file_format="csv",
        compression="none",
        object_store=store,
        session_factory=object(),
        settings=SimpleNamespace(type_infer_sample_rows=10, max_title_rows=3),
    )
    if scenario == "reupload_failure":
        args["existing_table_id"] = uuid4()
    if scenario.startswith("cancel"):
        with pytest.raises(asyncio.CancelledError):
            await parse.run_parse(**args)
    elif scenario.endswith("failure"):
        with pytest.raises(RuntimeError):
            await parse.run_parse(**args)
    else:
        returned = await parse.run_parse(**args)
        if scenario == "skip":
            assert returned == []
        else:
            assert len(returned) == 1
            assert Path(returned[0].local_parquet_path).read_bytes() == b"small local output"
            assert paths == [Path(returned[0].local_parquet_path)]
    if scenario not in {"success", "reservation"}:
        assert paths and all(not path.exists() for path in paths)
    assert source.read_bytes() == b"caller original"
    assert store.blobs["original"] == b"caller original"
    if scenario in {"table_failure", "later_table_failure", "later_version_failure", "reupload_failure"}:
        assert any(key != "original" for key in store.blobs), "durable materialised bytes must survive"


@pytest.mark.parametrize("file_format", ["csv", "json", "xlsx", "parquet", "arrow", "orc", "avro"])
async def test_registered_reader_accepts_reserved_empty_private_output(tmp_path, file_format):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from flyquery.core.services.ingestion.reader import TableExtractionRules
    from flyquery.core.services.ingestion.reader_factory import get_reader

    source = tmp_path / f"input.{file_format}"
    rows = [{"item": "A", "amount": 47}, {"item": "B", "amount": 99}]
    table = pa.Table.from_pylist(rows)
    if file_format == "csv":
        source.write_text("item,amount\nA,47\nB,99\n")
    elif file_format == "json":
        import json

        source.write_text(json.dumps(rows))
    elif file_format == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["item", "amount"])
        for row in rows:
            sheet.append(list(row.values()))
        workbook.save(source)
    elif file_format == "parquet":
        pq.write_table(table, source)
    elif file_format == "arrow":
        import pyarrow.ipc as ipc

        with pa.OSFile(str(source), "wb") as stream, ipc.new_stream(stream, table.schema) as writer:
            writer.write_table(table)
    elif file_format == "orc":
        import pyarrow.orc as orc

        orc.write_table(table, source)
    else:
        import fastavro

        schema = {
            "type": "record",
            "name": "Row",
            "fields": [
                {"name": "item", "type": "string"},
                {"name": "amount", "type": "long"},
            ],
        }
        with source.open("wb") as stream:
            fastavro.writer(stream, schema, rows)
    fd, target = tempfile.mkstemp(suffix=".parquet", dir=tmp_path)
    os.close(fd)
    assert stat.S_IMODE(Path(target).stat().st_mode) == 0o600
    reader = get_reader(file_format)
    proposed = await reader.enumerate_tables(str(source), TableExtractionRules())
    result = await reader.materialise(
        str(source),
        proposed[0],
        target,
        workspace_locale="en-US",
        type_infer_sample_rows=10,
    )
    assert result.n_rows_actual == 2
    assert pq.read_table(target).to_pylist() == rows
    assert stat.S_IMODE(Path(target).stat().st_mode) == 0o600
    assert source.exists()


@pytest.mark.parametrize("operation", ["rename", "read_sample", "profile", "references", "sample"])
async def test_stage_native_consumers_finish_before_cancellation_returns(monkeypatch, tmp_path, operation):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from flyquery.core.services.ingestion.stages import parse, profile, sample

    source = tmp_path / "owned.parquet"
    pq.write_table(pa.table({"amount": [47, 99]}), source)
    started = asyncio.Event()
    release, finished = threading.Event(), threading.Event()
    loop = asyncio.get_running_loop()

    def block(function):
        def call(*args, **kwargs):
            loop.call_soon_threadsafe(started.set)
            if not release.wait(5):
                raise RuntimeError("test did not release native consumer")
            try:
                assert source.exists()
                return function(*args, **kwargs)
            finally:
                finished.set()

        return call

    if operation in {"rename", "read_sample"}:
        monkeypatch.setattr(duckdb, "connect", block(duckdb.connect))
        if operation == "rename":
            pending = parse._rename_parquet_columns(
                parquet_path=str(source),
                current_columns=["amount"],
                proposed_columns=["value"],
            )
        else:
            pending = parse._read_parquet_sample(str(source))
    else:
        columns = [
            {
                "id": uuid4(),
                "qualified_name": "orders.amount",
                "data_type": "INTEGER",
                "pii_tag": "NONE",
                "description": None,
            }
        ]
        module = sample if operation == "sample" else profile
        monkeypatch.setattr(module, "_load_columns", AsyncMock(return_value=columns))
        if operation == "sample":
            monkeypatch.setattr(sample, "build_pii_scanner", lambda _: object())
            monkeypatch.setattr(sample, "_read_parquet_column", block(sample._read_parquet_column))
            pending = sample.run_sample(
                tenant_id="owned",
                snapshot_id=uuid4(),
                parquet_key=str(source),
                session_factory=object(),
                settings=SimpleNamespace(pii_scanner="none", sample_n=2),
            )
        else:
            name = "_profile_column_sync" if operation == "profile" else "_detect_self_references"
            monkeypatch.setattr(profile, name, block(getattr(profile, name)))
            pending = profile.run_profile(
                tenant_id="owned",
                snapshot_id=uuid4(),
                parquet_key=str(source),
                n_rows_actual=2,
                session_factory=object(),
                settings=SimpleNamespace(profile_row_threshold=10),
            )
    task = asyncio.create_task(pending)
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "stage returned while native consumer still owned its input path"
    finally:
        release.set()
        result = (await asyncio.gather(task, return_exceptions=True))[0]
        assert await asyncio.to_thread(finished.wait, 2)
    assert isinstance(result, asyncio.CancelledError)
    assert source.exists()


async def test_failed_native_rename_reclaims_only_its_private_sidecar(monkeypatch, tmp_path):
    import duckdb
    from flyquery.core.services.ingestion.stages import parse

    source = tmp_path / "owned.parquet"
    source.write_bytes(b"completed primary output")
    retained_sidecar = Path(str(source) + ".rename.tmp")
    retained_sidecar.write_bytes(b"pre-existing caller file")
    outputs = []
    original = tempfile.mkstemp

    def reserve(**kwargs):
        fd, path = original(**kwargs)
        outputs.append(Path(path))
        return fd, path

    class Connection:
        closed = False

        def execute(self, sql):
            if sql.startswith("COPY"):
                assert outputs, "rename output must be privately reserved"
                assert outputs[0].exists()
                assert stat.S_IMODE(outputs[0].stat().st_mode) == 0o600
                outputs[0].write_bytes(b"partial rewrite")
                raise RuntimeError("COPY failed")

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(tempfile, "mkstemp", reserve)
    monkeypatch.setattr(duckdb, "connect", lambda **kwargs: connection)
    with pytest.raises(RuntimeError, match="COPY failed"):
        await parse._rename_parquet_columns(
            parquet_path=str(source),
            current_columns=["amount"],
            proposed_columns=["value"],
        )
    assert connection.closed
    assert outputs and all(not output.exists() for output in outputs)
    assert source.read_bytes() == b"completed primary output"
    assert retained_sidecar.read_bytes() == b"pre-existing caller file"
