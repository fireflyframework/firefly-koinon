# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Raw pipeline copies are owned locally; durable uploads survive cleanup."""

import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

DATA = b"item,amount\nA,47\n"


class MemoryStore:
    def __init__(self):
        self.blobs = {}

    async def put(self, key, data, content_type):
        self.blobs[key] = data

    async def get(self, key):
        async def chunks():
            yield self.blobs[key]

        return chunks()


@pytest.fixture
def owned_copies(monkeypatch, tmp_path):
    original = tempfile.mkstemp
    copies = []

    def create(*args, **kwargs):
        kwargs["dir"] = tmp_path
        fd, name = original(*args, **kwargs)
        copies.append((fd, Path(name)))
        return fd, name

    monkeypatch.setattr(tempfile, "mkstemp", create)
    return copies


def receive_args(store):
    return dict(
        tenant_id="owned",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        filename="orders.csv",
        file_bytes=DATA,
        actor="owner",
        object_store=store,
        session_factory=object(),
        settings=SimpleNamespace(max_file_mb=1, max_workspace_gb=1),
        workspace_storage_used_bytes=0,
    )


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
async def test_receive_failed_insert_reclaims_only_local_copy(monkeypatch, owned_copies, failure):
    from flyquery.core.services.ingestion.stages import receive

    store = MemoryStore()
    monkeypatch.setattr(
        receive, "FileRepository", lambda _: SimpleNamespace(insert_received=AsyncMock(side_effect=failure()))
    )
    with pytest.raises(failure):
        await receive.run_receive(**receive_args(store))
    assert list(store.blobs.values()) == [DATA]
    assert len(owned_copies) == 1
    assert not owned_copies[0][1].exists()
    with pytest.raises(OSError):
        os.fstat(owned_copies[0][0])


async def test_receive_fdopen_failure_closes_descriptor_and_reclaims_copy(monkeypatch, owned_copies):
    from flyquery.core.services.ingestion.stages import receive

    store = MemoryStore()
    monkeypatch.setattr(receive.os, "fdopen", lambda *args: (_ for _ in ()).throw(OSError("open failed")))
    with pytest.raises(OSError, match="open failed"):
        await receive.run_receive(**receive_args(store))
    assert list(store.blobs.values()) == [DATA]
    assert not owned_copies[0][1].exists()
    with pytest.raises(OSError):
        os.fstat(owned_copies[0][0])


@pytest.mark.parametrize("method", ["ingest_upload", "ingest_reupload"])
@pytest.mark.parametrize("failure_at", [None, "track", "parse", "cancel"])
async def test_sync_ingestion_reclaims_received_copy(monkeypatch, owned_copies, method, failure_at):
    from flyquery.core.services.ingestion import ingest_service
    from flyquery.core.services.ingestion.stages import receive

    store = MemoryStore()
    monkeypatch.setattr(receive, "FileRepository", lambda _: SimpleNamespace(insert_received=AsyncMock()))
    service = object.__new__(ingest_service.IngestService)
    service._settings = SimpleNamespace(default_locale="en-US", max_file_mb=1, max_workspace_gb=1)
    service._object_store = store
    service._session_factory = object()
    service._workspace_service = SimpleNamespace(
        get=AsyncMock(return_value={"storage_used_bytes": 0}),
        track_storage=AsyncMock(side_effect=RuntimeError("track") if failure_at == "track" else None),
    )
    service._fetch_table_identifiers = AsyncMock(return_value=(None, None))

    async def parse(**kwargs):
        assert Path(kwargs["local_temp_path"]).read_bytes() == DATA
        if failure_at == "parse":
            raise RuntimeError("parse")
        if failure_at == "cancel":
            raise asyncio.CancelledError
        return []

    monkeypatch.setattr(ingest_service, "run_parse", parse)
    args = receive_args(store)
    for key in ("object_store", "session_factory", "settings", "workspace_storage_used_bytes"):
        args.pop(key)
    if method == "ingest_reupload":
        args["table_id"] = uuid4()
    if failure_at:
        with pytest.raises(asyncio.CancelledError if failure_at == "cancel" else RuntimeError):
            await getattr(service, method)(**args)
    else:
        result = await getattr(service, method)(**args)
        assert result.tables == []
    assert list(store.blobs.values()) == [DATA]
    assert len(owned_copies) == 1
    assert not owned_copies[0][1].exists()


@pytest.mark.parametrize(
    ("already_received", "failure_at"),
    [(already, failure) for already in (False, True) for failure in (None, "emit", "check", "parse", "cancel")]
    + [(False, "track"), (True, "detect")],
)
async def test_worker_reclaims_raw_copy_before_leaving_parse(
    monkeypatch, owned_copies, already_received, failure_at
):
    from flyquery.core.services.ingestion import format_detect, workers
    from flyquery.core.services.ingestion.stages import parse, receive
    from flyquery.core.services.storage import object_store_factory
    from flyquery.core.services.workspaces import workspace_repository, workspace_service

    store = MemoryStore()
    store.blobs["original.csv"] = DATA
    original_file_id = uuid4()
    monkeypatch.setattr(object_store_factory, "build_object_store", lambda _: store)
    monkeypatch.setattr(receive, "FileRepository", lambda _: SimpleNamespace(insert_received=AsyncMock()))
    monkeypatch.setattr(workspace_repository, "WorkspaceRepository", lambda _: object())
    tracked = []

    async def track(workspace_id, size):
        tracked.append(size)
        if failure_at == "track":
            raise RuntimeError("track")

    monkeypatch.setattr(
        workspace_service,
        "WorkspaceService",
        lambda _: SimpleNamespace(get=AsyncMock(return_value={"storage_used_bytes": 0}), track_storage=track),
    )
    worker = object.__new__(workers.IngestWorker)
    worker._settings = SimpleNamespace(default_locale="en-US", max_file_mb=1, max_workspace_gb=1)
    worker._session_factory = object()
    worker._ingest_publisher = object()
    worker._load_file = AsyncMock(
        return_value={"id": original_file_id, "object_store_key": "original.csv", "original_filename": "orders.csv"}
    )
    checks = 0

    async def check(job_id):
        nonlocal checks
        checks += 1
        if failure_at == "check" and checks == 3:
            raise asyncio.CancelledError

    worker._check_cancelled = check

    async def emit(**kwargs):
        if kwargs["stage"] == "received" and failure_at == "emit":
            raise RuntimeError("emit")
        if kwargs["stage"] == "parsed":
            assert not owned_copies[0][1].exists()

    monkeypatch.setattr(workers, "emit_stage", emit)

    async def run_parse(**kwargs):
        assert Path(kwargs["local_temp_path"]).read_bytes() == DATA
        if already_received:
            assert kwargs["file_id"] == original_file_id
        if failure_at == "parse":
            raise RuntimeError("parse")
        if failure_at == "cancel":
            raise asyncio.CancelledError
        return []

    monkeypatch.setattr(parse, "run_parse", run_parse)
    if failure_at == "detect":
        monkeypatch.setattr(format_detect, "detect_format", lambda *args: (_ for _ in ()).throw(ValueError("detect")))
    args = dict(
        job_id=uuid4(),
        tenant_id="owned",
        workspace_id=uuid4(),
        job={"dataset_id": uuid4(), "file_id": original_file_id, "request_json": {"already_received": already_received}},
    )
    if failure_at:
        error = asyncio.CancelledError if failure_at in ("check", "cancel") else ValueError if failure_at == "detect" else RuntimeError
        with pytest.raises(error):
            await worker._run_reparse(**args)
    else:
        await worker._run_reparse(**args)
    assert store.blobs["original.csv"] == DATA
    assert len(store.blobs) == (1 if already_received else 2)
    assert len(owned_copies) == 1
    assert not owned_copies[0][1].exists()
    if already_received:
        assert tracked == []


@pytest.mark.parametrize("failure_at", [None, "track", "enqueue", "cancel"])
async def test_async_controller_reclaims_copy_before_queueing(monkeypatch, owned_copies, failure_at):
    from flyquery.core.services.ingestion.stages import receive
    from flyquery.web.controllers import files_controller

    store = MemoryStore()
    monkeypatch.setattr(receive, "FileRepository", lambda _: SimpleNamespace(insert_received=AsyncMock()))
    workspace_id = uuid4()
    monkeypatch.setattr(
        files_controller,
        "tenant_context_from_request",
        lambda _: SimpleNamespace(tenant_id="owned", actor="owner", workspace_id=str(workspace_id)),
    )
    controller = object.__new__(files_controller.FilesController)
    controller._object_store = store
    controller._settings = SimpleNamespace(max_file_mb=1, max_workspace_gb=1)
    controller._session_factory = object()
    controller._datasets = SimpleNamespace(get=AsyncMock(return_value={"name": "orders"}))

    async def track(*args):
        assert not owned_copies[0][1].exists()
        if failure_at == "track":
            raise RuntimeError("track")

    async def enqueue(**kwargs):
        assert not owned_copies[0][1].exists()
        if failure_at == "enqueue":
            raise RuntimeError("enqueue")
        if failure_at == "cancel":
            raise asyncio.CancelledError
        return SimpleNamespace(id=uuid4())

    controller._workspaces = SimpleNamespace(get=AsyncMock(return_value={"storage_used_bytes": 0}), track_storage=track)
    controller._ingest_jobs = SimpleNamespace(enqueue_parse_and_ingest=enqueue, mark_already_received=AsyncMock())
    upload = SimpleNamespace(filename="orders.csv", read=AsyncMock(return_value=DATA))
    request = SimpleNamespace(form=AsyncMock(return_value={"file": upload}), headers={})
    if failure_at:
        with pytest.raises(asyncio.CancelledError if failure_at == "cancel" else RuntimeError):
            await controller.upload_file_async(request, uuid4())
    else:
        response = await controller.upload_file_async(request, uuid4())
        assert response.status_code == 202
    assert list(store.blobs.values()) == [DATA]
    assert not owned_copies[0][1].exists()


@pytest.mark.parametrize("failure", [None, RuntimeError, asyncio.CancelledError])
async def test_parse_preserves_caller_original(monkeypatch, tmp_path, failure):
    from flyquery.core.services.ingestion.stages import parse

    original = tmp_path / "user-original.csv"
    original.write_bytes(DATA)

    async def enumerate_tables(path, rules):
        assert Path(path).read_bytes() == DATA
        if failure:
            raise failure()
        return []

    monkeypatch.setattr(parse, "get_reader", lambda **kwargs: SimpleNamespace(enumerate_tables=enumerate_tables))
    monkeypatch.setattr(parse.lineage, "emit", AsyncMock())
    args = dict(
        tenant_id="owned",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        file_id=uuid4(),
        local_temp_path=str(original),
        file_format="csv",
        compression="none",
        object_store=MemoryStore(),
        session_factory=object(),
        settings=SimpleNamespace(),
    )
    if failure:
        with pytest.raises(failure):
            await parse.run_parse(**args)
    else:
        assert await parse.run_parse(**args) == []
    assert original.read_bytes() == DATA
