# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import hashlib

import httpx
import pytest

from koinon_sdk import KoinonClient


class StreamingReceipt(httpx.AsyncBaseTransport):
    def __init__(self, digest, size):
        self.digest, self.size = digest, size
        self.requests = []
        self.blocks = []

    async def handle_async_request(self, request):
        self.requests.append(request)
        actual, count = hashlib.sha256(), 0
        async for block in request.stream:
            self.blocks.append(len(block))
            actual.update(block)
            count += len(block)
        assert count == self.size and actual.hexdigest() == self.digest
        assert request.headers["content-length"] == str(self.size)
        assert request.headers["idempotency-key"] == "original-key"
        assert request.headers["authorization"] == "Bearer current-token"
        assert request.headers["content-type"] == "application/octet-stream"
        return httpx.Response(
            200,
            json={
                "receipt_id": "receipt",
                "batch_id": "batch",
                "item_id": "item",
                "sha256": self.digest,
                "size_bytes": count,
            },
        )


async def test_path_helper_streams_over_32_mib_in_bounded_blocks_with_exact_manifest(tmp_path):
    path = tmp_path / "large.xlsx"
    size = 33 * 1024**2
    with path.open("wb") as output:
        output.truncate(size)
    digest = hashlib.sha256()
    for _ in range(size // 65536):
        digest.update(bytes(65536))
    transport = StreamingReceipt(digest.hexdigest(), size)
    async with KoinonClient(
        "https://owned.test/api/v1", token_provider=lambda: "current-token", transport=transport
    ) as client:
        result = await client.upload_file_batch_path(
            "north/office",
            "batch",
            "item",
            path,
            "original-key",
            expected_size_bytes=size,
            expected_sha256=digest.hexdigest(),
        )
    assert result.size_bytes == size and len(transport.requests) == 1
    assert max(transport.blocks) == 65536 and len(transport.blocks) == 528
    assert b"north%2Foffice" in transport.requests[0].url.raw_path


@pytest.mark.parametrize("change", ["size", "digest", "symlink"])
async def test_invalid_local_original_never_opens_a_request(tmp_path, change):
    path = tmp_path / "original"
    path.write_bytes(b"evidence")
    size, digest = 8, hashlib.sha256(b"evidence").hexdigest()
    if change == "size":
        size += 1
    elif change == "digest":
        digest = "0" * 64
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(path)
        path = alias
    transport = StreamingReceipt(digest, size)
    async with KoinonClient(
        "https://owned.test/api/v1", token_provider=lambda: "current-token", transport=transport
    ) as client:
        with pytest.raises(ValueError):
            await client.upload_file_batch_path(
                "north",
                "batch",
                "item",
                path,
                "original-key",
                expected_size_bytes=size,
                expected_sha256=digest,
            )
    assert not transport.requests


async def test_cancelled_upload_closes_owned_file_and_has_no_automatic_replay(tmp_path, monkeypatch):
    from koinon_sdk import file_upload

    path = tmp_path / "original"
    path.write_bytes(b"evidence")
    entered, files, requests = asyncio.Event(), [], []
    fdopen = file_upload.os.fdopen

    def tracked(*args, **kwargs):
        stream = fdopen(*args, **kwargs)
        files.append(stream)
        return stream

    class Blocked(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            requests.append(request)
            async for _ in request.stream:
                entered.set()
                await asyncio.Event().wait()
            raise AssertionError("The upload must be cancelled")

    monkeypatch.setattr(file_upload.os, "fdopen", tracked)
    async with KoinonClient(
        "https://owned.test/api/v1", token_provider=lambda: "current-token", transport=Blocked()
    ) as client:
        task = asyncio.create_task(
            client.upload_file_batch_path(
                "north",
                "batch",
                "item",
                path,
                "original-key",
                expected_size_bytes=8,
                expected_sha256=hashlib.sha256(b"evidence").hexdigest(),
            )
        )
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(requests) == 1 and files and all(stream.closed for stream in files)


@pytest.mark.parametrize("replace", [False, True])
async def test_source_mutation_after_preparation_cannot_change_transmitted_bytes(tmp_path, replace):
    path = tmp_path / "original"
    path.write_bytes(b"evidence")
    digest = hashlib.sha256(b"evidence").hexdigest()

    class Mutating(StreamingReceipt):
        async def handle_async_request(self, request):
            if replace:
                path.rename(tmp_path / "retained")
            path.write_bytes(b"changed!")
            return await super().handle_async_request(request)

    transport = Mutating(digest, 8)
    async with KoinonClient(
        "https://owned.test/api/v1", token_provider=lambda: "current-token", transport=transport
    ) as client:
        await client.upload_file_batch_path(
            "north", "batch", "item", path, "original-key", expected_size_bytes=8, expected_sha256=digest
        )
    assert len(transport.requests) == 1 and path.read_bytes() == b"changed!"


async def test_cancelled_preparation_drains_worker_and_closes_snapshot_before_return(tmp_path, monkeypatch):
    import threading

    from koinon_sdk import file_upload

    path = tmp_path / "original"
    path.write_bytes(b"evidence")
    entered, release, prepared = threading.Event(), threading.Event(), []
    original = file_upload._snapshot

    def blocked(*args):
        entered.set()
        assert release.wait(5)
        snapshot = original(*args)
        prepared.append(snapshot)
        return snapshot

    monkeypatch.setattr(file_upload, "_snapshot", blocked)
    transport = StreamingReceipt(hashlib.sha256(b"evidence").hexdigest(), 8)
    async with KoinonClient(
        "https://owned.test/api/v1", token_provider=lambda: "current-token", transport=transport
    ) as client:
        task = asyncio.create_task(
            client.upload_file_batch_path(
                "north",
                "batch",
                "item",
                path,
                "original-key",
                expected_size_bytes=8,
                expected_sha256=transport.digest,
            )
        )
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert prepared and all(snapshot.closed for snapshot in prepared)
    assert not transport.requests
