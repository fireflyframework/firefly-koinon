# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Transferred local Parquet copies remain owned until all consumers finish."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


def parsed_output(tmp_path, index):
    path = tmp_path / f"owned-{index}.parquet"
    path.write_bytes(b"local completed output")
    return SimpleNamespace(
        local_parquet_path=str(path), parquet_key=f"durable/{index}.parquet", table_id=uuid4(),
        name=f"section_{index}", lineage_receipt=None,
    )


@pytest.mark.parametrize("failure_at", [None, "reconcile", "embed", "publish", "cancel", "waiting"])
async def test_sync_section_reclaims_its_output_on_every_exit(monkeypatch, tmp_path, failure_at):
    from flyquery.core.services.ingestion import ingest_service

    parsed = parsed_output(tmp_path, 0)
    original = tmp_path / "caller-original.csv"
    original.write_bytes(b"original upload")
    durable = {"original": b"original upload", parsed.parquet_key: b"durable snapshot"}
    service = object.__new__(ingest_service.IngestService)
    service._stage_semaphore = asyncio.Semaphore(0 if failure_at == "waiting" else 1)
    service._session_factory = object()
    service._settings = SimpleNamespace(allow_provider_fallback=False)
    service._publisher = object()

    async def reconcile(**kwargs):
        if failure_at == "reconcile":
            raise RuntimeError("reconcile")
        return SimpleNamespace(snapshot_id=uuid4(), n_columns=1, n_rows_actual=1)

    async def embed(**kwargs):
        if failure_at == "embed":
            raise RuntimeError("embed")
        if failure_at == "cancel":
            raise asyncio.CancelledError

    async def publish(**kwargs):
        durable["published"] = b"published snapshot"
        if failure_at == "publish":
            raise RuntimeError("publish")

    for name in ("run_sample", "run_profile", "run_describe"):
        monkeypatch.setattr(ingest_service, name, AsyncMock())
    monkeypatch.setattr(ingest_service, "run_reconcile", reconcile)
    monkeypatch.setattr(ingest_service, "run_embed", embed)
    monkeypatch.setattr(ingest_service, "run_publish", publish)
    args = dict(tenant_id="owned", workspace_id=uuid4(), dataset_id=uuid4(), actor="owner", parsed=parsed)
    if failure_at == "waiting":
        task = asyncio.create_task(service._process_section(**args))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    elif failure_at:
        with pytest.raises(asyncio.CancelledError if failure_at == "cancel" else RuntimeError):
            await service._process_section(**args)
    else:
        result = await service._process_section(**args)
        assert result.table_id == str(parsed.table_id)
    assert not Path(parsed.local_parquet_path).exists()
    assert original.read_bytes() == b"original upload"
    assert durable["original"] == b"original upload"
    assert durable[parsed.parquet_key] == b"durable snapshot"
    if failure_at in {None, "publish"}:
        assert durable["published"] == b"published snapshot"


@pytest.mark.parametrize("failure_at", [None, "emit", "reconcile", "later_reconcile", "embed", "publish", "cancel"])
async def test_worker_reclaims_all_returned_outputs_including_unvisited_sections(
    monkeypatch, tmp_path, failure_at
):
    from flyquery.core.services.ingestion import workers
    from flyquery.core.services.ingestion.stages import embed, parse, publish, reconcile
    from flyquery.core.services.storage import object_store_factory
    from flyquery.core.services.workspaces import workspace_repository, workspace_service

    outputs = [parsed_output(tmp_path, index) for index in range(2)]
    durable = {"original.csv": b"original upload", **{item.parquet_key: b"durable snapshot" for item in outputs}}

    async def get(key):
        async def chunks():
            yield durable[key]

        return chunks()

    monkeypatch.setattr(object_store_factory, "build_object_store", lambda _: SimpleNamespace(get=get))
    monkeypatch.setattr(workspace_repository, "WorkspaceRepository", lambda _: object())
    monkeypatch.setattr(
        workspace_service, "WorkspaceService",
        lambda _: SimpleNamespace(get=AsyncMock(return_value={"storage_used_bytes": 0})),
    )
    worker = object.__new__(workers.IngestWorker)
    worker._settings = SimpleNamespace(default_locale="en-US")
    worker._session_factory = object()
    worker._ingest_publisher = object()
    worker._check_cancelled = AsyncMock()
    file_id = uuid4()
    worker._load_file = AsyncMock(return_value={
        "id": file_id, "object_store_key": "original.csv", "original_filename": "orders.csv",
    })
    monkeypatch.setattr(parse, "run_parse", AsyncMock(return_value=outputs))

    async def emit_stage(**kwargs):
        if kwargs["stage"] == "parsed" and failure_at == "emit":
            raise RuntimeError("parsed event")

    count = 0

    async def run_reconcile(**kwargs):
        nonlocal count
        count += 1
        if failure_at == "reconcile" or failure_at == "later_reconcile" and count == 2:
            raise RuntimeError("reconcile")
        return SimpleNamespace(snapshot_id=uuid4(), n_columns=1, n_rows_actual=1)

    async def run_embed(**kwargs):
        if failure_at == "embed":
            raise RuntimeError("embed")
        if failure_at == "cancel":
            raise asyncio.CancelledError

    async def run_publish(**kwargs):
        durable["published"] = b"published snapshot"
        if failure_at == "publish":
            raise RuntimeError("publish")

    monkeypatch.setattr(workers, "emit_stage", emit_stage)
    monkeypatch.setattr(reconcile, "run_reconcile", run_reconcile)
    monkeypatch.setattr(embed, "run_embed", run_embed)
    monkeypatch.setattr(publish, "run_publish", run_publish)
    args = dict(
        job_id=uuid4(), tenant_id="owned", workspace_id=uuid4(), job={
            "dataset_id": uuid4(), "file_id": file_id, "request_json": {"already_received": True},
        },
    )
    if failure_at:
        with pytest.raises(asyncio.CancelledError if failure_at == "cancel" else RuntimeError):
            await worker._run_reparse(**args)
    else:
        await worker._run_reparse(**args)
    assert all(not Path(item.local_parquet_path).exists() for item in outputs)
    assert durable["original.csv"] == b"original upload"
    assert all(durable[item.parquet_key] == b"durable snapshot" for item in outputs)
    if failure_at in {None, "publish", "later_reconcile"}:
        assert durable["published"] == b"published snapshot"


@pytest.mark.parametrize("method", ["ingest_upload", "ingest_reupload"])
async def test_sync_cancel_before_section_tasks_start_reclaims_returned_outputs(monkeypatch, tmp_path, method):
    from flyquery.core.services.ingestion import ingest_service

    outputs = [parsed_output(tmp_path, index) for index in range(2)]
    raw = tmp_path / "received.csv"
    raw.write_bytes(b"raw upload copy")
    received = SimpleNamespace(
        file_id=uuid4(), local_temp_path=str(raw), file_format="csv", compression="none", size_bytes=15,
    )
    monkeypatch.setattr(ingest_service, "run_receive", AsyncMock(return_value=received))

    async def parse(**kwargs):
        asyncio.current_task().cancel()
        return outputs

    monkeypatch.setattr(ingest_service, "run_parse", parse)
    service = object.__new__(ingest_service.IngestService)
    service._settings = SimpleNamespace(default_locale="en-US")
    service._workspace_service = SimpleNamespace(get=AsyncMock(return_value=None), track_storage=AsyncMock())
    service._object_store = object()
    service._session_factory = object()
    service._stage_semaphore = asyncio.Semaphore(0)
    service._fetch_table_identifiers = AsyncMock(return_value=(None, None))
    args = dict(
        tenant_id="owned", workspace_id=uuid4(), dataset_id=uuid4(), filename="orders.csv",
        file_bytes=b"raw upload copy", actor="owner",
    )
    if method == "ingest_reupload":
        args["table_id"] = uuid4()
    task = asyncio.create_task(getattr(service, method)(**args))
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not raw.exists()
    assert all(not Path(output.local_parquet_path).exists() for output in outputs)


async def test_sync_failed_section_keeps_running_sibling_output_until_it_finishes(monkeypatch, tmp_path):
    from flyquery.core.services.ingestion import ingest_service

    outputs = [parsed_output(tmp_path, index) for index in range(2)]
    service = object.__new__(ingest_service.IngestService)
    service._stage_semaphore = asyncio.Semaphore(2)
    service._session_factory = object()
    service._settings = SimpleNamespace(allow_provider_fallback=False)
    service._publisher = object()
    started, release = asyncio.Event(), asyncio.Event()

    async def reconcile(**kwargs):
        if kwargs["parsed"] is outputs[0]:
            raise RuntimeError("first section failed")
        started.set()
        await release.wait()
        assert Path(outputs[1].local_parquet_path).exists()
        return SimpleNamespace(snapshot_id=uuid4(), n_columns=1, n_rows_actual=1)

    monkeypatch.setattr(ingest_service, "run_reconcile", reconcile)
    for name in ("run_sample", "run_profile", "run_describe", "run_embed", "run_publish"):
        monkeypatch.setattr(ingest_service, name, AsyncMock())
    tasks = [service._start_section(
        tenant_id="owned", workspace_id=uuid4(), dataset_id=uuid4(), actor="owner", parsed=output,
    ) for output in outputs]
    try:
        with pytest.raises(RuntimeError, match="first section failed"):
            await asyncio.gather(*tasks)
        await asyncio.wait_for(started.wait(), timeout=2)
        assert not tasks[1].done()
        assert Path(outputs[1].local_parquet_path).exists()
        assert not Path(outputs[0].local_parquet_path).exists()
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert all(not Path(output.local_parquet_path).exists() for output in outputs)
