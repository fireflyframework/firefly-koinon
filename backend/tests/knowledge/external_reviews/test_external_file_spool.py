# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
from types import SimpleNamespace

import pytest
from pyfly.core import Config

from koinon.knowledge.external_reviews.file_storage import ExternalReviewFileStorage
from koinon.storage.local import LocalBlobStore
from koinon.storage.scratch import ScratchAdmission


@pytest.fixture
async def staged(tmp_path):
    root = tmp_path / "objects"
    root.mkdir(mode=0o700)
    store = LocalBlobStore(str(root))
    storage = ExternalReviewFileStorage(
        SimpleNamespace(
            get=lambda: SimpleNamespace(
                configured=lambda: store, profile=SimpleNamespace(max_object_bytes=128 * 1024**2)
            )
        ),
        ScratchAdmission(Config({})),
    )
    row = SimpleNamespace(
        tenant_id="north",
        subject="issuer|owner",
        credential_id="token",
        id="review",
        blob_reference_json=None,
    )
    chunks = [b"a" * 65536, b"last chunk"]
    row.chunks_json = {}
    for index, content in enumerate(chunks):
        digest = hashlib.sha256(content).hexdigest()
        await storage.put(row, f"chunks/{index}", content, digest)
        row.chunks_json[str(index)] = {"size": len(content), "sha256": digest}
    return storage, store, row, b"".join(chunks)


async def test_seal_streams_chunks_and_retains_exact_provider_reference(staged, tmp_path, monkeypatch):
    storage, store, row, content = staged
    original_read = store.get_bounded

    async def bounded_chunks(key, maximum):
        assert "/chunks/" in key
        assert maximum <= 65536
        return await original_read(key, maximum)

    monkeypatch.setattr(store, "get_bounded", bounded_chunks)
    reference = await storage.seal_file(row, len(content), hashlib.sha256(content).hexdigest())
    assert reference.key == storage.key(row, "original")
    row.blob_reference_json = reference.to_dict()
    target = tmp_path / "downloaded"
    await storage.download(row, target, len(content), reference.sha256)
    assert target.read_bytes() == content


async def test_changed_route_cannot_supply_a_sealed_original(staged, tmp_path):
    storage, store, row, content = staged
    digest = hashlib.sha256(content).hexdigest()
    row.blob_reference_json = (await storage.seal_file(row, len(content), digest)).to_dict()
    other = tmp_path / "other"
    other.mkdir(mode=0o700)
    replacement = LocalBlobStore(str(other))
    await replacement.put(storage.key(row, "original"), content)
    storage.attachments.get().configured = lambda: replacement
    storage.attachments = SimpleNamespace(
        get=lambda: SimpleNamespace(
            configured=lambda: replacement, profile=SimpleNamespace(max_object_bytes=128 * 1024**2)
        )
    )
    target = tmp_path / "untrusted"
    with pytest.raises(OSError):
        await storage.download(row, target, len(content), digest)
    assert not target.exists()


async def test_corrupted_chunk_never_publishes_original(staged):
    storage, store, row, content = staged
    await store.put(storage.key(row, "chunks/0"), b"b" * 65536)
    with pytest.raises((ValueError, OSError)):
        await storage.seal_file(row, len(content), hashlib.sha256(content).hexdigest())
    assert not store._path(storage.key(row, "original")).exists()


async def test_cancelled_file_transfer_drains_before_owned_scratch_is_removed(staged, tmp_path, monkeypatch):
    import asyncio
    import threading

    storage, store, row, content = staged
    digest = hashlib.sha256(content).hexdigest()
    row.blob_reference_json = (await storage.seal_file(row, len(content), digest)).to_dict()
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    from koinon_storage import local_files

    original = local_files.download_file

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        result = original(*args, **kwargs)
        completed.set()
        return result

    monkeypatch.setattr(local_files, "download_file", blocked)
    target = tmp_path / "transfer"
    task = asyncio.create_task(storage.download(row, target, len(content), digest))
    assert await asyncio.to_thread(entered.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert completed.is_set()
    assert target.read_bytes() == content
