# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Spreadsheet inputs retain all admitted rows without materializing whole Python grids."""

import builtins
from pathlib import Path

import pytest


def test_delimited_coordinates_stream_physical_lines_without_readlines(tmp_path, monkeypatch):
    import duckdb

    from flyquery.core.services.ingestion.readers.delimited import materialize

    source = tmp_path / "input.csv"
    source.write_text('id,label\n1,"first\nsecond"\n2,last\n')
    original = builtins.open

    class Stream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def __iter__(self):
            return iter(self.stream)

        def readlines(self, *args):
            raise AssertionError("Whole-file line materialization is forbidden")

        def __getattr__(self, name):
            return getattr(self.stream, name)

    def opened(path, *args, **kwargs):
        stream = original(path, *args, **kwargs)
        return Stream(stream) if Path(path) == source and "b" not in (args[0] if args else "") else stream

    monkeypatch.setattr(builtins, "open", opened)
    connection = duckdb.connect()
    try:
        receipt = materialize(connection, str(source), str(tmp_path / "out.parquet"), sample_rows=2048)
        assert receipt.complete and tuple(receipt.record_indices) == (1, 2)
    finally:
        connection.close()


def test_coordinate_positions_keep_million_contiguous_rows_as_one_span():
    from flyquery.core.services.ingestion.readers.delimited import RecordPositions

    positions = RecordPositions()
    for row in range(1, 1_000_001):
        positions.append(row)
    assert len(positions) == 1_000_000 and positions.span_count == 1
    assert positions[:3] == (1, 2, 3) and positions[-1] == 1_000_000


def test_ooxml_sparse_used_rectangle_is_rejected_before_native_sheet_allocation(tmp_path):
    from zipfile import ZipFile

    from flyquery.core.services.ingestion.readers.excel_bounds import preflight
    from flyquery.core.services.ingestion.resources import IngestionResourceLimitError

    path = tmp_path / "sparse.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml", '<worksheet><dimension ref="A1:XFD1048576"/><sheetData/></worksheet>'
        )
    with pytest.raises(IngestionResourceLimitError, match="shape"):
        preflight(str(path))


def test_disk_rows_preserve_scalar_types_and_slices_without_whole_grid(tmp_path):
    from datetime import UTC, date, datetime, time, timedelta

    from flyquery.core.services.ingestion.readers.excel_bounds import DiskRows

    values = [
        None,
        "",
        True,
        17,
        1.25,
        date(2026, 1, 2),
        datetime(2026, 1, 2, tzinfo=UTC),
        time(3, 4),
        timedelta(days=2),
    ]
    with DiskRows(iter([[""] * 9, values, values])) as rows:
        assert len(rows) == 2 and rows.leading_empty == 1 and rows[0] == values
        assert rows[:][1] == values and not isinstance(rows[:], list)


def test_reader_rss_limit_drains_owned_child_and_preserves_existing_output(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import psutil

    from flyquery.core.services.ingestion.reader import ProposedTable
    from flyquery.core.services.ingestion.readers import excel_process
    from flyquery.core.services.ingestion.resources import IngestionResourceLimitError, resource_scope

    source = tmp_path / "invalid.xlsx"
    source.write_bytes(b"not an archive")
    target = tmp_path / "original.parquet"
    target.write_bytes(b"preserved existing result")
    pids = []
    original = excel_process.subprocess.Popen

    def launch(*args, **kwargs):
        process = original(*args, **kwargs)
        pids.append(process.pid)
        return process

    monkeypatch.setattr(excel_process.subprocess, "Popen", launch)
    with (
        resource_scope(SimpleNamespace(ingest_scratch_root=str(tmp_path), ingest_reader_rss_max_bytes=1)),
        pytest.raises(IngestionResourceLimitError, match="memory"),
    ):
        excel_process.execute(
            "materialise", (str(source), ProposedTable("t", "t", 1, 1), str(target), "en-US", 1000, 3)
        )
    assert target.read_bytes() == b"preserved existing result"
    assert pids and all(not psutil.pid_exists(pid) for pid in pids)
    assert not list(tmp_path.glob("flyquery-*"))


async def test_reader_cancellation_drains_child_before_return_and_removes_all_owned_scratch(
    tmp_path, monkeypatch
):
    import asyncio
    from types import SimpleNamespace

    import psutil

    from flyquery.core.services.ingestion.reader import TableExtractionRules
    from flyquery.core.services.ingestion.readers import excel_process
    from flyquery.core.services.ingestion.resources import resource_scope

    source = tmp_path / "input.xlsx"
    source.write_bytes(b"not an archive")
    started = asyncio.Event()
    loop = asyncio.get_running_loop()
    original = excel_process.subprocess.Popen
    pids = []

    def launch(*args, **kwargs):
        process = original(*args, **kwargs)
        pids.append(process.pid)
        loop.call_soon_threadsafe(started.set)
        return process

    monkeypatch.setattr(excel_process.subprocess, "Popen", launch)
    with resource_scope(SimpleNamespace(ingest_scratch_root=str(tmp_path))):
        task = asyncio.create_task(
            excel_process.execute_async("enumerate", (str(source), TableExtractionRules()))
        )
        await asyncio.wait_for(started.wait(), 2)
        task.cancel("caller cancellation")
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
    assert pids and all(not psutil.pid_exists(pid) for pid in pids)
    assert not list(tmp_path.glob("flyquery-*"))


def test_preflight_worksheet_xml_uses_total_expansion_budget_not_shared_string_budget(tmp_path):
    from types import SimpleNamespace
    from zipfile import ZIP_DEFLATED, ZipFile

    from flyquery.core.services.ingestion.readers.excel_bounds import preflight
    from flyquery.core.services.ingestion.resources import IngestionResourceLimitError, resource_scope

    path = tmp_path / "expanded.xlsx"
    worksheet = '<worksheet><dimension ref="A1:B2"/><sheetData>' + (" " * 8192) + "</sheetData></worksheet>"
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
        archive.writestr("xl/sharedStrings.xml", "<sst/>")
    with resource_scope(
        SimpleNamespace(ingest_decompressed_max_bytes=16384, ingest_shared_strings_max_bytes=128)
    ):
        preflight(str(path))
    with (
        resource_scope(SimpleNamespace(ingest_decompressed_max_bytes=4096)),
        pytest.raises(IngestionResourceLimitError, match="expanded"),
    ):
        preflight(str(path))
    shared = tmp_path / "shared.xlsx"
    with ZipFile(shared, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", "<sst>" + (" " * 256) + "</sst>")
    with (
        resource_scope(SimpleNamespace(ingest_shared_strings_max_bytes=128)),
        pytest.raises(IngestionResourceLimitError, match="expanded"),
    ):
        preflight(str(shared))


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_ooxml_dtd_rejected_before_any_entity_expansion(tmp_path, encoding):
    from zipfile import ZipFile

    from flyquery.core.services.ingestion.readers.excel_bounds import preflight
    from flyquery.core.services.ingestion.resources import IngestionResourceLimitError

    path = tmp_path / "entities.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                f'<?xml version="1.0" encoding="{encoding}"?><!DOCTYPE worksheet [<!ENTITY e "private">]><worksheet>&e;</worksheet>'
            ).encode(encoding),
        )
    with pytest.raises(IngestionResourceLimitError, match="entity"):
        preflight(str(path))


def test_new_reader_environment_limits_are_strict_and_reach_native_resource_policy(monkeypatch):
    from pydantic import ValidationError

    from flyquery.config import FlyquerySettings
    from flyquery.core.services.ingestion.resources import IngestionResourcePolicy

    monkeypatch.setenv("FLYQUERY_INGEST_READER_RSS_MAX_BYTES", "805306368")
    monkeypatch.setenv("FLYQUERY_INGEST_READER_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("FLYQUERY_INGEST_EXCEL_MAX_CELLS", "2000000")
    monkeypatch.setenv("FLYQUERY_INGEST_SHARED_STRINGS_MAX_BYTES", "33554432")
    policy = IngestionResourcePolicy.from_settings(FlyquerySettings(_env_file=None))
    assert policy.reader_rss_max_bytes == 805306368 and policy.reader_timeout_seconds == 120
    assert policy.excel_max_cells == 2000000 and policy.shared_strings_max_bytes == 33554432
    with pytest.raises(ValidationError):
        FlyquerySettings(ingest_reader_timeout_seconds=True, _env_file=None)


def test_content_type_declared_worksheet_with_custom_part_name_cannot_bypass_shape_preflight(tmp_path):
    from zipfile import ZipFile

    from flyquery.core.services.ingestion.readers.excel_bounds import preflight
    from flyquery.core.services.ingestion.resources import IngestionResourceLimitError

    path = tmp_path / "custom-part.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/custom-part.data" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        )
        archive.writestr(
            "xl/custom-part.data",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:XFD1048576"/><sheetData/></worksheet>',
        )
    with pytest.raises(IngestionResourceLimitError, match="shape"):
        preflight(str(path))


def test_custom_shared_strings_part_retains_its_tighter_expansion_budget(tmp_path):
    from types import SimpleNamespace
    from zipfile import ZipFile

    from flyquery.core.services.ingestion.readers.excel_bounds import preflight
    from flyquery.core.services.ingestion.resources import IngestionResourceLimitError, resource_scope

    path = tmp_path / "custom-strings.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types><Override PartName="/xl/custom-strings.data" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>',
        )
        archive.writestr("xl/custom-strings.data", "<sst>" + (" " * 256) + "</sst>")
    with (
        resource_scope(SimpleNamespace(ingest_shared_strings_max_bytes=128)),
        pytest.raises(IngestionResourceLimitError, match="expanded"),
    ):
        preflight(str(path))


def test_owned_child_kernel_deadline_remains_active_without_parent_monitor(tmp_path):
    import os
    import signal
    import subprocess
    import sys
    import time

    if not hasattr(signal, "SIGALRM"):
        pytest.skip("Kernel alarm qualification targets the managed POSIX runtime")
    script = "from flyquery.core.services.ingestion.readers.excel_process import _self_limits;import os,time;_self_limits(os.getppid(),1);time.sleep(10)"
    start = time.monotonic()
    process = subprocess.Popen([sys.executable, "-c", script], env=os.environ.copy())
    try:
        assert process.wait(timeout=3) == -signal.SIGALRM
        assert time.monotonic() - start < 3
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


async def test_linux_child_is_terminated_when_only_its_immediate_parent_dies(tmp_path):
    import asyncio
    import os
    import subprocess
    import sys

    import psutil

    if sys.platform != "linux":
        pytest.skip("Linux parent-death signal qualification")
    ready = tmp_path / "child.ready"
    child_script = (
        "from flyquery.core.services.ingestion.readers.excel_process import _self_limits;"
        "import os,time;from pathlib import Path;_self_limits(os.getppid(),10);"
        f"Path({str(ready)!r}).write_text(str(os.getpid()));time.sleep(10)"
    )
    parent_script = (
        f'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",{child_script!r}]);time.sleep(10)'
    )
    parent = subprocess.Popen([sys.executable, "-c", parent_script], env=os.environ.copy())
    child_pid = None
    try:
        for _ in range(100):
            if ready.exists():
                break
            await asyncio.sleep(0.02)
        assert ready.exists()
        child_pid = int(ready.read_text())
        parent.kill()
        parent.wait()
        for _ in range(100):
            if not psutil.pid_exists(child_pid) or psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE:
                break
            await asyncio.sleep(0.02)
        assert not psutil.pid_exists(child_pid) or psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()
        if (
            child_pid
            and psutil.pid_exists(child_pid)
            and psutil.Process(child_pid).status() != psutil.STATUS_ZOMBIE
        ):
            psutil.Process(child_pid).kill()


def test_duckdb_spill_files_share_the_same_accounted_scratch_budget(tmp_path):
    from types import SimpleNamespace

    from flyquery.core.services.ingestion.resources import (
        IngestionResourceLimitError,
        connect,
        resource_scope,
    )

    with resource_scope(
        SimpleNamespace(
            ingest_scratch_root=str(tmp_path),
            ingest_scratch_max_bytes=4096,
            ingest_decompressed_max_bytes=4096,
            ingest_native_connections=1,
        )
    ):
        connection = connect()
        try:
            (Path(connection.directory.name) / "owned-spill").write_bytes(b"x" * 8192)
            with pytest.raises(IngestionResourceLimitError, match="scratch"):
                connection.scope.check()
        finally:
            connection.close()


def test_child_budget_carves_parent_originals_and_completed_outputs(tmp_path):
    from types import SimpleNamespace

    from flyquery.core.services.ingestion.resources import IngestionResourceLimitError, resource_scope

    source = tmp_path / "original"
    source.write_bytes(b"123")
    completed = tmp_path / "completed"
    completed.write_bytes(b"1234")
    with resource_scope(
        SimpleNamespace(ingest_scratch_max_bytes=100, ingest_decompressed_max_bytes=100)
    ) as scope:
        scope.account(completed)
        with scope.child_budget(source) as allocation:
            assert allocation.maximum == 96
            assert scope.usage() == 100
            with pytest.raises(IngestionResourceLimitError), scope.child_budget(source):
                pass
        assert scope.usage() == 7


def test_live_native_scratch_overrun_is_terminated_before_publication(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace

    import psutil

    from flyquery.core.services.ingestion.reader import TableExtractionRules
    from flyquery.core.services.ingestion.readers import excel_process
    from flyquery.core.services.ingestion.resources import IngestionResourceLimitError, resource_scope

    source = tmp_path / "source.xlsx"
    source.write_bytes(b"x")
    original = excel_process.subprocess.Popen
    processes = []

    def launch(arguments, **options):
        request = arguments[-2]
        script = (
            "import json,time;from pathlib import Path;"
            f"r=json.loads(Path({request!r}).read_text());"
            '(Path(r["policy"]["scratch_root"])/"native-spill").write_bytes(bytes(8192));time.sleep(10)'
        )
        process = original([sys.executable, "-c", script], **options)
        processes.append(process)
        return process

    monkeypatch.setattr(excel_process.subprocess, "Popen", launch)
    with (
        resource_scope(
            SimpleNamespace(
                ingest_scratch_root=str(tmp_path),
                ingest_scratch_max_bytes=4096,
                ingest_decompressed_max_bytes=4096,
            )
        ),
        pytest.raises(IngestionResourceLimitError, match="scratch"),
    ):
        excel_process.execute("enumerate", (str(source), TableExtractionRules()))
    assert processes and all(not psutil.pid_exists(process.pid) for process in processes)
    assert not list(tmp_path.glob("flyquery-*"))
