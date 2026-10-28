# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType

import pytest

PART = 5 * 1024 * 1024


def adapter(monkeypatch, client):
    # Exercise the real adapter against a protocol double without requiring the optional cloud SDK.
    for package in ("aiobotocore", "botocore"):
        if importlib.util.find_spec(package) is None:
            module = ModuleType(package)
            child = ModuleType(package + (".session" if package == "aiobotocore" else ".config"))
            setattr(module, "session" if package == "aiobotocore" else "config", child)
            child.Config = lambda **kwargs: kwargs
            monkeypatch.setitem(sys.modules, package, module)
            monkeypatch.setitem(sys.modules, child.__name__, child)
    path = Path(__file__).parents[3] / "packages/structured/src/flyquery/core/services/storage/adapters/s3.py"
    spec = importlib.util.spec_from_file_location("_owned_structured_s3_protocol_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    store = module.S3ObjectStore.__new__(module.S3ObjectStore)
    store._bucket, store._prefix = "owned-test", "private"

    @asynccontextmanager
    async def connection():
        yield client

    async def connect():
        return connection()

    store._client = connect
    return store


class Client:
    def __init__(self):
        self.parts = []
        self.aborted = False
        self.completed = False

    async def head_bucket(self, **kwargs):
        return {}

    async def create_multipart_upload(self, **kwargs):
        return {"UploadId": "owned-upload"}

    async def upload_part(self, **kwargs):
        self.parts.append(kwargs["Body"])
        return {"ETag": str(len(self.parts))}

    async def complete_multipart_upload(self, **kwargs):
        self.completed = True

    async def abort_multipart_upload(self, **kwargs):
        self.aborted = True

    async def put_object(self, **kwargs):
        self.empty = kwargs["Body"]


async def test_small_input_chunks_are_aggregated_to_valid_s3_parts(monkeypatch):
    client = Client()
    store = adapter(monkeypatch, client)

    async def chunks():
        for _ in range(81):
            yield b"x" * 65536

    receipt = await store.put("file.parquet", chunks(), "application/octet-stream")
    assert [len(part) for part in client.parts] == [PART, 65536]
    assert receipt.size_bytes == PART + 65536 and client.completed and not client.aborted


async def test_stream_failure_aborts_multipart_and_preserves_original_error(monkeypatch):
    client = Client()
    store = adapter(monkeypatch, client)

    async def chunks():
        yield b"x" * PART
        raise RuntimeError("Owned stream failure")

    with pytest.raises(RuntimeError, match="Owned stream failure"):
        await store.put("file.parquet", chunks(), "application/octet-stream")
    assert client.aborted and not client.completed


async def test_cancellation_aborts_multipart(monkeypatch):
    import asyncio

    client = Client()
    store = adapter(monkeypatch, client)

    async def chunks():
        yield b"x" * PART
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await store.put("file.parquet", chunks(), "application/octet-stream")
    assert client.aborted and not client.completed


async def test_large_single_chunk_splits_and_empty_stream_has_no_invalid_completion(monkeypatch):
    client = Client()
    store = adapter(monkeypatch, client)

    async def chunks():
        yield b"x" * (PART * 2 + 17)

    receipt = await store.put("file.parquet", chunks(), "application/octet-stream")
    assert [len(part) for part in client.parts] == [PART, PART, 17]
    assert receipt.size_bytes == PART * 2 + 17

    async def empty():
        yield b""

    client.completed = False
    receipt = await store.put("empty.parquet", empty(), "application/octet-stream")
    assert receipt.size_bytes == 0 and client.aborted and not client.completed and client.empty == b""
