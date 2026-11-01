# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owned file/SDK protocol fixtures only; no cloud resources or credentials."""

from hashlib import sha256
from types import SimpleNamespace

import pytest

from koinon_storage.cloud import CloudProfile, CloudStore, ObjectIntegrityError
from koinon_storage.files import StoredObjectReference


class OwnedBlob:
    def __init__(self):
        self.data = b""
        self.metadata = {}
        self.etag = "version-one"
        self.writes = 0

    def upload_blob(self, source, **options):
        assert options["overwrite"] is False and options["max_concurrency"] == 1
        assert hasattr(source, "read") and options["length"] == 8
        self.data = b"".join(iter(lambda: source.read(65536), b""))
        self.metadata = options["metadata"]
        self.writes += 1

    def get_blob_properties(self, **options):
        return SimpleNamespace(size=len(self.data), metadata=self.metadata, etag=self.etag)

    def download_blob(self, **options):
        assert options["etag"] == self.etag
        assert options["length"] <= 9
        return SimpleNamespace(chunks=lambda: iter((self.data[:3], self.data[3:])))


def store(blob, *, prefix="pending"):
    return CloudStore(
        CloudProfile(
            backend="azure",
            azure_account_url="https://owned.blob.core.windows.net",
            azure_container="owned-private",
            azure_prefix=prefix,
            max_object_bytes=1024,
        ),
        client=SimpleNamespace(get_blob_client=lambda **options: blob),
        owns_client=False,
    )


async def test_file_transport_streams_create_and_read_and_pins_version_and_route(tmp_path):
    blob = OwnedBlob()
    native = store(blob)
    source = tmp_path / "upload"
    source.write_bytes(b"original")
    ref = await native.create_file("tenant/workspace/job/original", source, content_type="text/plain")
    assert isinstance(ref, StoredObjectReference) and ref.sha256 == sha256(b"original").hexdigest()
    assert ref.version == "version-one" and ref.size_bytes == 8
    assert StoredObjectReference.from_dict(ref.to_dict()) == ref
    target = tmp_path / "download"
    await native.download_file(ref, target, max_bytes=8)
    assert target.read_bytes() == b"original" and blob.writes == 1
    with pytest.raises(ObjectIntegrityError):
        await store(blob, prefix="changed-route").download_file(ref, tmp_path / "wrong", max_bytes=8)
    assert not (tmp_path / "wrong").exists()
    blob.etag = "version-two"
    with pytest.raises(ObjectIntegrityError):
        await native.download_file(ref, tmp_path / "changed", max_bytes=8)
    assert not (tmp_path / "changed").exists()


async def test_corrupt_persisted_bytes_leave_no_scratch_and_do_not_accept_a_new_digest(tmp_path):
    blob = OwnedBlob()
    native = store(blob)
    source = tmp_path / "upload"
    source.write_bytes(b"original")
    ref = await native.create_file("tenant/workspace/job/original", source)
    blob.data = b"altered!"
    with pytest.raises(ObjectIntegrityError):
        await native.download_file(ref, tmp_path / "partial", max_bytes=8)
    assert not (tmp_path / "partial").exists()


class OwnedGCS:
    def __init__(self):
        self.data = b""
        self.generation = 7
        self.metadata = {}
        self.size = 0

    def upload_from_file(self, source, **options):
        assert options["if_generation_match"] == 0 and options["retry"] is None
        assert options["size"] == 8
        self.data = b"".join(iter(lambda: source.read(65536), b""))
        self.size = len(self.data)

    def reload(self, **options):
        assert options["retry"] is None

    def download_to_file(self, sink, **options):
        assert options["if_generation_match"] == self.generation and options["retry"] is None
        sink.write(self.data[:3])
        sink.write(self.data[3:])


async def test_gcs_file_transport_uses_conditional_create_and_exact_generation(tmp_path):
    blob = OwnedGCS()
    native = CloudStore(
        CloudProfile(backend="gcs", gcs_bucket="owned-private", max_object_bytes=1024),
        client=SimpleNamespace(bucket=lambda name: SimpleNamespace(blob=lambda key: blob)),
        owns_client=False,
    )
    source = tmp_path / "upload"
    source.write_bytes(b"original")
    reference = await native.create_file("t/w/original", source)
    assert reference.version_kind == "gcs_generation" and reference.version == "7"
    await native.download_file(reference, tmp_path / "restored", max_bytes=8)
    assert (tmp_path / "restored").read_bytes() == b"original"
    blob.generation = 8
    with pytest.raises(ObjectIntegrityError):
        await native.download_file(reference, tmp_path / "changed", max_bytes=8)
    assert not (tmp_path / "changed").exists()


async def test_cancelled_file_upload_drains_sdk_and_close_without_replay(tmp_path):
    import asyncio
    import threading

    entered, release = threading.Event(), threading.Event()

    class BlockingBlob(OwnedBlob):
        def upload_blob(self, source, **options):
            entered.set()
            assert release.wait(5)
            super().upload_blob(source, **options)

    blob = BlockingBlob()
    native = store(blob)
    source = tmp_path / "upload"
    source.write_bytes(b"original")
    task = asyncio.create_task(native.create_file("t/w/original", source))
    try:
        while not entered.is_set():
            await asyncio.sleep(0.01)
        task.cancel()
        closing = asyncio.create_task(native.close())
        await asyncio.sleep(0.03)
        assert not task.done() and not closing.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await closing
    assert blob.writes == 1 and blob.data == b"original"


async def test_create_collision_never_replaces_the_original_or_accepts_different_bytes(tmp_path):
    blob = OwnedBlob()
    native = store(blob)
    source = tmp_path / "upload"
    source.write_bytes(b"original")
    await native.create_file("t/w/original", source)

    class Conflict(Exception):
        status_code = 409

    def collision(*args, **kwargs):
        raise Conflict()

    blob.upload_blob = collision
    source.write_bytes(b"modified")
    with pytest.raises(ObjectIntegrityError):
        await native.create_file("t/w/original", source)
    assert blob.data == b"original" and blob.writes == 1
