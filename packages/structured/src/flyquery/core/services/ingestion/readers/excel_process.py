# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owned spreadsheet processes have bounded lifetime, sampled RSS, and private results."""

import asyncio
import contextvars
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import suppress
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Literal, overload

import psutil

from flyquery.core.services.ingestion.coordinates import ColumnOrigin, MaterializationCoordinates, RowRange
from flyquery.core.services.ingestion.reader import ColumnSchema, MaterialiseResult, ProposedTable
from flyquery.core.services.ingestion.resources import (
    IngestionResourceLimitError,
    current_scope,
    directory_bytes,
)

RESULT_BYTES = 8 * 1024**2


def _restore(value) -> MaterialiseResult:
    coordinates = value.get("coordinates")
    if coordinates is not None:
        coordinates["row_ranges"] = tuple(RowRange(**span) for span in coordinates["row_ranges"])
        coordinates["columns"] = tuple(
            ColumnOrigin(
                **(
                    column
                    | {
                        "source_path": tuple(column["source_path"]),
                        "header_cells": tuple(tuple(cell) for cell in column["header_cells"]),
                    }
                )
            )
            for column in coordinates["columns"]
        )
        for key in ("parser_decisions", "dependencies"):
            coordinates[key] = tuple(tuple(item) for item in coordinates[key])
        for key in ("source_path", "rejected_source_rows"):
            coordinates[key] = tuple(coordinates[key])
        value["coordinates"] = MaterializationCoordinates(**coordinates)
    value["columns"] = tuple(ColumnSchema(**column) for column in value["columns"])
    return MaterialiseResult(**value)


@overload
def execute(
    operation: Literal["enumerate"], arguments: tuple[Any, ...], stop=None
) -> list[ProposedTable]: ...


@overload
def execute(
    operation: Literal["materialise"], arguments: tuple[Any, ...], stop=None
) -> MaterialiseResult: ...


def execute(
    operation: Literal["enumerate", "materialise"], arguments: tuple[Any, ...], stop=None
) -> list[ProposedTable] | MaterialiseResult:
    parent = current_scope()
    policy = parent.policy
    with (
        parent.child_budget(arguments[0]) as allocation,
        tempfile.TemporaryDirectory(prefix="flyquery-reader-", dir=policy.scratch_root) as directory,
    ):
        root = Path(directory).resolve()
        output = root / "result.json"
        args = list(arguments)
        destination = None
        if operation == "materialise":
            args[1] = asdict(args[1])
            destination = Path(args[2])
            args[2] = str(root / "output.parquet")
        else:
            args[1] = asdict(args[1])
        request = root / "request.json"
        request.write_text(
            json.dumps(
                {
                    "operation": operation,
                    "arguments": args,
                    "policy": asdict(policy)
                    | {
                        "scratch_root": str(root),
                        "scratch_max_bytes": allocation.maximum,
                        "decompressed_max_bytes": min(policy.decompressed_max_bytes, allocation.maximum),
                    },
                    "owner_pid": os.getpid(),
                }
            )
        )
        environment = {
            name: value
            for name, value in os.environ.items()
            if name in {"PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "PYTHONPATH"}
        }
        environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.Popen(
            [sys.executable, "-m", __name__, str(request), str(output)],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        start = time.monotonic()
        try:
            with suppress(psutil.NoSuchProcess):
                observed = psutil.Process(process.pid)
            while process.poll() is None:
                if stop is not None and stop.is_set():
                    raise IngestionResourceLimitError("Spreadsheet parsing was cancelled")
                if time.monotonic() - start > policy.reader_timeout_seconds:
                    raise IngestionResourceLimitError("Spreadsheet parsing exceeded its time budget")
                try:
                    rss = observed.memory_info().rss
                except psutil.NoSuchProcess:
                    break
                if rss > policy.reader_rss_max_bytes:
                    raise IngestionResourceLimitError("Spreadsheet parsing exceeded its memory budget")
                if directory_bytes(root) + Path(arguments[0]).stat().st_size > allocation.maximum:
                    raise IngestionResourceLimitError("Spreadsheet parsing exceeded its scratch budget")
                time.sleep(0.02)
            if process.wait() != 0 or not output.is_file() or output.stat().st_size > RESULT_BYTES:
                raise IngestionResourceLimitError("Spreadsheet parsing did not produce a bounded result")
            value = json.loads(output.read_text())
            if "error" in value:
                if value["error"] == "resource":
                    raise IngestionResourceLimitError("Spreadsheet exceeds configured parser resources")
                raise ValueError("Spreadsheet parsing failed; input is invalid or unsupported")
            if operation == "enumerate":
                return [ProposedTable(**table) for table in value]
            if stop is not None and stop.is_set():
                raise IngestionResourceLimitError("Spreadsheet parsing was cancelled")
            if destination is None:
                raise ValueError("Spreadsheet output destination is missing")
            result = _restore(value)
            if Path(args[2]).stat().st_size != result.parquet_byte_size:
                raise IngestionResourceLimitError("Spreadsheet result size changed before publication")
            allocation.publish(Path(args[2]), destination, result.parquet_byte_size)
            return replace(result, target_parquet_key=str(destination))
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


@overload
async def execute_async(
    operation: Literal["enumerate"], arguments: tuple[Any, ...]
) -> list[ProposedTable]: ...


@overload
async def execute_async(
    operation: Literal["materialise"], arguments: tuple[Any, ...]
) -> MaterialiseResult: ...


async def execute_async(
    operation: Literal["enumerate", "materialise"], arguments: tuple[Any, ...]
) -> list[ProposedTable] | MaterialiseResult:
    stop = threading.Event()
    context = contextvars.copy_context()

    def invoke():
        if operation == "enumerate":
            return context.run(execute, "enumerate", arguments, stop)
        return context.run(execute, "materialise", arguments, stop)

    future = asyncio.get_running_loop().run_in_executor(None, invoke)
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        stop.set()
        while not future.done():
            try:
                await asyncio.shield(future)
            except asyncio.CancelledError:
                continue
            except BaseException:
                break
        with suppress(BaseException):
            future.result()
        raise


def _self_limits(owner_pid: int, wall_seconds: int) -> None:
    from koinon_storage.process_guard import arm_parent_bound_deadline

    try:
        arm_parent_bound_deadline(wall_seconds, owner_pid)
    except (OSError, ValueError, RuntimeError, AttributeError) as error:
        raise IngestionResourceLimitError("Spreadsheet child lifecycle protection is unavailable") from error


def _main():
    import socket
    from types import SimpleNamespace

    from flyquery.core.services.ingestion.reader import TableExtractionRules
    from flyquery.core.services.ingestion.readers.excel_reader import ExcelReader
    from flyquery.core.services.ingestion.resources import resource_scope

    def offline(*args, **kwargs):
        raise PermissionError("Spreadsheet parsing has no network access")

    socket.socket.connect = offline
    socket.socket.connect_ex = offline
    socket.create_connection = offline
    request, output = Path(sys.argv[1]), Path(sys.argv[2])
    if request.stat().st_size > 64 * 1024:
        raise ValueError("Reader request exceeds its metadata budget")
    value = json.loads(request.read_text())
    settings = SimpleNamespace(**{"ingest_" + key: item for key, item in value["policy"].items()})
    settings.ingest_duckdb_memory_limit = value["policy"]["memory_limit"]
    settings.ingest_duckdb_threads = value["policy"]["threads"]
    try:
        _self_limits(value["owner_pid"], value["policy"]["reader_timeout_seconds"])
        with resource_scope(settings) as scope:
            scope.owned_directory(settings.ingest_scratch_root)
            args = value["arguments"]
            if value["operation"] == "enumerate":
                args[1] = TableExtractionRules(**args[1])
                result = [asdict(table) for table in ExcelReader._enumerate_local(*args)]
            elif value["operation"] == "materialise":
                args[1] = ProposedTable(**args[1])
                result = asdict(ExcelReader._materialise_local(*args))
            else:
                raise ValueError("Unsupported internal reader operation")
            encoded = json.dumps(result, ensure_ascii=False)
            if len(encoded.encode()) > RESULT_BYTES:
                raise IngestionResourceLimitError("Reader result exceeds its metadata budget")
            scope.account(output, len(encoded.encode()))
            output.write_text(encoded)
            scope.check()
            return
    except IngestionResourceLimitError:
        encoded = '{"error":"resource"}'
    except Exception:
        encoded = '{"error":"invalid"}'
    output.write_text(encoded)


if __name__ == "__main__":
    _main()
