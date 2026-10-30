# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Cleanup failures cannot interrupt transfer of locally owned parser outputs."""

import asyncio
import gc
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


def output(tmp_path, index):
    path = tmp_path / f"owned-{index}.parquet"
    path.write_bytes(b"completed output")
    return SimpleNamespace(
        local_parquet_path=str(path), parquet_key=f"durable/{index}", table_id=uuid4(),
        name=f"section_{index}", lineage_receipt=None,
    )


def service(monkeypatch, received, parsed):
    from flyquery.core.services.ingestion import ingest_service

    monkeypatch.setattr(ingest_service, "run_receive", AsyncMock(return_value=received))
    monkeypatch.setattr(ingest_service, "run_parse", parsed)
    instance = object.__new__(ingest_service.IngestService)
    instance._settings = SimpleNamespace(default_locale="en-US", allow_provider_fallback=False)
    instance._workspace_service = SimpleNamespace(get=AsyncMock(return_value=None), track_storage=AsyncMock())
    instance._object_store = object()
    instance._publisher = object()
    instance._session_factory = object()
    instance._stage_semaphore = asyncio.Semaphore(1)
    instance._fetch_table_identifiers = AsyncMock(return_value=(None, None))
    monkeypatch.setattr(ingest_service, "run_reconcile", AsyncMock(return_value=SimpleNamespace(
        snapshot_id=uuid4(), n_columns=1, n_rows_actual=1,
    )))
    for name in ("run_sample", "run_profile", "run_describe", "run_embed", "run_publish"):
        monkeypatch.setattr(ingest_service, name, AsyncMock())
    return instance


def arguments(method):
    args = dict(
        tenant_id="owned", workspace_id=uuid4(), dataset_id=uuid4(), filename="orders.csv",
        file_bytes=b"original upload", actor="owner",
    )
    if method == "ingest_reupload":
        args["table_id"] = uuid4()
    return args


@pytest.mark.parametrize("route", ["ingest_upload", "ingest_reupload", "worker"])
@pytest.mark.parametrize(
    ("primary", "deny_output"),
    [(None, False), (None, True), (ValueError, False), (asyncio.CancelledError, False)],
)
async def test_raw_unlink_error_reclaims_transferred_outputs_and_preserves_primary(
    monkeypatch, tmp_path, route, primary, deny_output, caplog
):
    outputs = [output(tmp_path, index) for index in range(2)] if primary is None else []
    fd, raw_name = tempfile.mkstemp(suffix=".csv", dir=tmp_path)
    raw = Path(raw_name)
    if route != "worker":
        os.close(fd)
    cleanup_error = PermissionError("controlled raw cleanup failure")
    primary_error = primary("primary parse failure") if primary else None
    durable = {"original.csv": b"original upload", **{item.parquet_key: b"durable output" for item in outputs}}
    before = dict(durable)

    async def parse(**kwargs):
        if primary_error is not None:
            raise primary_error
        return outputs

    if route == "worker":
        from flyquery.core.services.ingestion import workers
        from flyquery.core.services.ingestion.stages import parse as parse_module
        from flyquery.core.services.storage import object_store_factory
        from flyquery.core.services.workspaces import workspace_repository, workspace_service

        async def get(key):
            async def chunks():
                yield durable[key]

            return chunks()

        monkeypatch.setattr(tempfile, "mkstemp", lambda **kwargs: (fd, str(raw)))
        monkeypatch.setattr(object_store_factory, "build_object_store", lambda _: SimpleNamespace(get=get))
        monkeypatch.setattr(workspace_repository, "WorkspaceRepository", lambda _: object())
        monkeypatch.setattr(workspace_service, "WorkspaceService", lambda _: SimpleNamespace(get=AsyncMock(return_value=None)))
        instance = object.__new__(workers.IngestWorker)
        instance._settings = SimpleNamespace(default_locale="en-US")
        instance._session_factory = object()
        instance._check_cancelled = AsyncMock()
        file_id = uuid4()
        instance._load_file = AsyncMock(return_value={
            "id": file_id, "object_store_key": "original.csv", "original_filename": "orders.csv",
        })
        monkeypatch.setattr(workers, "emit_stage", AsyncMock())
        monkeypatch.setattr(parse_module, "run_parse", parse)
        operation = instance._run_reparse(
            job_id=uuid4(), tenant_id="owned", workspace_id=uuid4(), job={
                "dataset_id": uuid4(), "file_id": file_id, "request_json": {"already_received": True},
            },
        )
    else:
        received = SimpleNamespace(file_id=uuid4(), local_temp_path=str(raw), file_format="csv", compression="none", size_bytes=15)
        instance = service(monkeypatch, received, parse)
        operation = getattr(instance, route)(**arguments(route))
    unlink = Path.unlink

    def controlled_unlink(path, *args, **kwargs):
        if path == raw:
            raise cleanup_error
        if deny_output and path == Path(outputs[0].local_parquet_path):
            raise PermissionError("controlled owned output cleanup failure")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", controlled_unlink)
    try:
        with pytest.raises(primary if primary else PermissionError) as caught:
            await operation
        assert caught.value is (primary_error if primary else cleanup_error)
        assert all(not Path(item.local_parquet_path).exists() for item in outputs[1 if deny_output else 0:])
        if deny_output:
            assert Path(outputs[0].local_parquet_path).exists()
            assert any("local_parquet_cleanup_failed" in record.message for record in caplog.records)
        assert durable == before
    finally:
        unlink(raw, missing_ok=True)
        for item in outputs:
            unlink(Path(item.local_parquet_path), missing_ok=True)


@pytest.mark.parametrize("method", ["ingest_upload", "ingest_reupload"])
async def test_section_setup_failure_reclaims_only_unassigned_outputs(monkeypatch, tmp_path, method):
    outputs = [output(tmp_path, index) for index in range(2)]
    raw = tmp_path / "received.csv"
    raw.write_bytes(b"raw copy")
    received = SimpleNamespace(file_id=uuid4(), local_temp_path=str(raw), file_format="csv", compression="none", size_bytes=8)
    instance = service(monkeypatch, received, AsyncMock(return_value=outputs))
    instance._stage_semaphore = asyncio.Semaphore(0)
    submit = asyncio.create_task
    tasks, rejected = [], []

    def create_task(coroutine, **kwargs):
        if tasks:
            rejected.append(coroutine)
            raise RuntimeError("second section setup failed")
        task = submit(coroutine, **kwargs)
        tasks.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", create_task)
    try:
        with pytest.raises(RuntimeError, match="second section setup failed"):
            await getattr(instance, method)(**arguments(method))
        assert Path(outputs[0].local_parquet_path).exists()
        assert not tasks[0].done()
        assert not Path(outputs[1].local_parquet_path).exists()
        assert rejected[0].cr_frame is None, "unscheduled section coroutine was not closed"
    finally:
        for coroutine in rejected:
            coroutine.close()
        instance._stage_semaphore.release()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert all(not Path(item.local_parquet_path).exists() for item in outputs)


async def test_defensive_post_parse_table_bound_reclaims_returned_outputs(monkeypatch, tmp_path):
    from pyfly.kernel import PayloadTooLargeException

    outputs = [output(tmp_path, index) for index in range(2)]
    raw = tmp_path / "received.csv"
    raw.write_bytes(b"raw copy")
    received = SimpleNamespace(file_id=uuid4(), local_temp_path=str(raw), file_format="csv", compression="none", size_bytes=8)
    instance = service(monkeypatch, received, AsyncMock(return_value=outputs))
    with pytest.raises(PayloadTooLargeException):
        await instance.ingest_upload(**arguments("ingest_upload"), max_tables=1)
    assert all(not Path(item.local_parquet_path).exists() for item in outputs)


@pytest.mark.parametrize("failure_at", ["insert", "materialise"])
async def test_parser_cleanup_denial_preserves_primary_and_attempts_other_owned_outputs(
    monkeypatch, tmp_path, failure_at
):
    from flyquery.core.services.ingestion.reader import MaterialiseResult, ProposedTable
    from flyquery.core.services.ingestion.stages import parse

    source = tmp_path / "original.csv"
    source.write_bytes(b"original upload")
    paths = []
    reserve = tempfile.mkstemp
    unlink = Path.unlink
    primary = ValueError("primary parser failure")
    durable = {}

    def mkstemp(**kwargs):
        fd, path = reserve(**{**kwargs, "dir": tmp_path})
        paths.append(Path(path))
        return fd, path

    def controlled_unlink(path, *args, **kwargs):
        if paths and path == paths[0]:
            raise PermissionError("controlled output cleanup denial")
        return unlink(path, *args, **kwargs)

    class Reader:
        async def enumerate_tables(self, *args):
            return [ProposedTable(f"section_{i}", None, 0, 1) for i in range(2)]

        async def materialise(self, source, table, target, **kwargs):
            Path(target).write_bytes(b"completed output")
            if failure_at == "materialise":
                raise primary
            return MaterialiseResult(target, 16, 1, ())

    async def propose(**kwargs):
        return kwargs["mat_result"]

    async def insert(**kwargs):
        if kwargs["name"] == "section_1":
            raise primary
        return kwargs["table_id"]

    async def put(key, body, content_type):
        durable[key] = body

    monkeypatch.setattr(tempfile, "mkstemp", mkstemp)
    monkeypatch.setattr(Path, "unlink", controlled_unlink)
    monkeypatch.setattr(parse, "get_reader", lambda **kwargs: Reader())
    monkeypatch.setattr(parse, "_next_version", AsyncMock(return_value=1))
    monkeypatch.setattr(parse, "_insert_table", insert)
    monkeypatch.setattr(parse, "_propose_meaningful_column_names", propose)
    monkeypatch.setattr(parse.lineage, "emit", AsyncMock(return_value=None))
    try:
        with pytest.raises(ValueError) as caught:
            await parse.run_parse(
                tenant_id="owned", workspace_id=uuid4(), dataset_id=uuid4(), file_id=uuid4(),
                local_temp_path=str(source), file_format="csv", compression="none",
                object_store=SimpleNamespace(put=put), session_factory=object(),
                settings=SimpleNamespace(type_infer_sample_rows=10, max_title_rows=3),
                append_only=True,
            )
        assert caught.value is primary
        assert paths[0].exists()
        assert all(not path.exists() for path in paths[1:])
        assert source.read_bytes() == b"original upload"
        assert len(durable) == (2 if failure_at == "insert" else 0)
    finally:
        for path in paths:
            unlink(path, missing_ok=True)


async def test_setup_failure_observes_eventual_running_sibling_exception(monkeypatch, tmp_path):
    from flyquery.core.services.ingestion import ingest_service

    outputs = [output(tmp_path, index) for index in range(2)]
    raw = tmp_path / "received.csv"
    raw.write_bytes(b"raw copy")
    received = SimpleNamespace(file_id=uuid4(), local_temp_path=str(raw), file_format="csv", compression="none", size_bytes=8)
    instance = service(monkeypatch, received, AsyncMock(return_value=outputs))
    instance._stage_semaphore = asyncio.Semaphore(0)
    monkeypatch.setattr(ingest_service, "run_reconcile", AsyncMock(side_effect=RuntimeError("orphaned stage failure")))
    submit = asyncio.create_task
    tasks = []
    done = asyncio.Event()

    def create_task(coroutine, **kwargs):
        if tasks:
            raise RuntimeError("second section setup failed")
        task = submit(coroutine, **kwargs)
        task.add_done_callback(lambda _: done.set())
        tasks.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", create_task)
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    unobserved = []
    loop.set_exception_handler(lambda _loop, context: unobserved.append(context))
    try:
        with pytest.raises(RuntimeError, match="second section setup failed"):
            await instance.ingest_upload(**arguments("ingest_upload"))
        instance._stage_semaphore.release()
        await asyncio.wait_for(done.wait(), timeout=2)
        assert not Path(outputs[0].local_parquet_path).exists()
        tasks.clear()
        for _ in range(3):
            await asyncio.sleep(0)
            gc.collect()
        assert not any("exception was never retrieved" in context.get("message", "") for context in unobserved)
    finally:
        loop.set_exception_handler(previous_handler)
        if tasks:
            instance._stage_semaphore.release()
            await asyncio.gather(*tasks, return_exceptions=True)
