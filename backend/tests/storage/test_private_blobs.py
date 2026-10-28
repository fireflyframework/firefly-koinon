# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest


async def test_independent_instances_preserve_legacy_attachment_keys_and_bytes(tmp_path):
    from koinon.knowledge.attachments.settings import AttachmentSettings
    from koinon.knowledge.attachments.storage import AttachmentStorage
    from koinon.storage.settings import AttachmentStorageProfile

    content = b"retained private original"
    row = SimpleNamespace(
        id=str(uuid4()),
        tenant_id="tenant",
        subject="issuer|owner",
        thread_id="thread",
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
    )
    legacy = AttachmentSettings(storage_root=str(tmp_path / "private"))
    original = AttachmentStorage(legacy)
    await original.put(row, content)
    second = AttachmentStorage(AttachmentSettings(), AttachmentStorageProfile(root=legacy.storage_root))
    assert second.key(row) == original.key(row)
    assert await second.read(row) == content
    assert (tmp_path / "private").stat().st_mode & 0o077 == 0
    await second.purge(row)
    with pytest.raises(Exception) as error:
        await original.read(row)
    assert error.value.code == "ATTACHMENT_ORIGINAL_UNAVAILABLE"


async def test_admission_verifies_digest_before_writing_and_bounds_reads(tmp_path):
    from koinon.storage.local import LocalBlobStore
    from koinon.storage.ports import BlobTooLargeError, admit

    store = LocalBlobStore(str(tmp_path / "private"))
    content = b"private bytes"
    with pytest.raises(ValueError):
        await admit(
            store, "namespace/file/original", content, sha256=sha256(b"wrong").hexdigest(), max_bytes=64
        )
    assert not (tmp_path / "private" / "namespace/file/original").exists()
    receipt = await admit(
        store, "namespace/file/original", content, sha256=sha256(content).hexdigest(), max_bytes=64
    )
    assert receipt.size_bytes == len(content) and receipt.sha256 == sha256(content).hexdigest()
    with pytest.raises(BlobTooLargeError):
        await store.get_bounded("namespace/file/original", 2)


def test_conflicting_or_public_roots_fail_closed(tmp_path):
    from koinon.knowledge.attachments.settings import AttachmentSettings
    from koinon.knowledge.attachments.storage import AttachmentStorage
    from koinon.storage.settings import AttachmentStorageProfile

    with pytest.raises(ValueError, match="root"):
        AttachmentStorage(
            AttachmentSettings(storage_root=str(tmp_path / "old")),
            AttachmentStorageProfile(root=str(tmp_path / "new")),
        ).configured()


async def test_lowered_object_limit_returns_governed_error_for_retained_blob(tmp_path):
    from pyfly.kernel import ConflictException

    from koinon.knowledge.attachments.settings import AttachmentSettings
    from koinon.knowledge.attachments.storage import AttachmentStorage
    from koinon.storage.settings import AttachmentStorageProfile

    content = b"retained private original"
    row = SimpleNamespace(
        id=str(uuid4()),
        tenant_id="tenant",
        subject="issuer|owner",
        thread_id="thread",
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
    )
    settings = AttachmentSettings(storage_root=str(tmp_path / "private"))
    await AttachmentStorage(settings).put(row, content)
    narrowed = AttachmentStorage(settings, AttachmentStorageProfile(max_object_bytes=1))
    with pytest.raises(ConflictException) as error:
        await narrowed.read(row)
    assert error.value.code == "ATTACHMENT_ORIGINAL_UNAVAILABLE"


class S3Client:
    def __init__(self):
        self.objects = {}
        self.calls = []
        self.stream = None

    def put_object(self, **kwargs):
        self.calls.append(("put", kwargs))
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, **kwargs):
        self.calls.append(("get", kwargs))
        self.stream = BytesIO(self.objects[kwargs["Key"]])
        return {"ContentLength": len(self.objects[kwargs["Key"]]), "Body": self.stream}

    def delete_object(self, **kwargs):
        self.calls.append(("delete", kwargs))
        self.objects.pop(kwargs["Key"], None)


async def test_s3_protocol_preserves_private_keys_bounded_reads_and_closed_streams():
    from koinon.storage.ports import BlobTooLargeError, admit
    from koinon.storage.s3 import S3BlobStore
    from koinon.storage.settings import AttachmentStorageProfile

    client = S3Client()
    store = S3BlobStore(
        AttachmentStorageProfile(backend="s3", s3_bucket="private-test", s3_prefix="files"), client=client
    )
    content = b"private payload"
    receipt = await admit(
        store, "opaque/file/original", content, sha256=sha256(content).hexdigest(), max_bytes=64
    )
    assert receipt.sha256 == sha256(content).hexdigest()
    assert await store.get_bounded("opaque/file/original", 64) == content
    assert client.stream.closed
    put = client.calls[0][1]
    assert put["Key"] == "files/opaque/file/original" and "ACL" not in put
    assert put["Metadata"]["sha256"] == sha256(content).hexdigest()
    with pytest.raises(BlobTooLargeError):
        await store.get_bounded("opaque/file/original", 1)
    assert client.stream.closed
    await store.delete("opaque/file/original")
    assert not client.objects


async def test_failed_local_publish_preserves_previous_original(tmp_path, monkeypatch):
    import os

    from koinon.storage.local import LocalBlobStore

    store = LocalBlobStore(str(tmp_path / "private"))
    await store.put("namespace/file/original", b"retained bytes")

    def fail(*args):
        raise OSError("Owned local publish failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        await store.put("namespace/file/original", b"replacement")
    assert await store.get_bounded("namespace/file/original", 64) == b"retained bytes"
    assert not list((tmp_path / "private" / "namespace/file").glob(".staging-*"))


@pytest.mark.parametrize("key", ["../escape", "/absolute", "a/../b", "a//b", "a\\b", "a/./b"])
async def test_local_and_s3_reject_unregistered_keys(tmp_path, key):
    from koinon.storage.local import LocalBlobStore
    from koinon.storage.s3 import S3BlobStore
    from koinon.storage.settings import AttachmentStorageProfile

    stores = [
        LocalBlobStore(str(tmp_path / "private")),
        S3BlobStore(
            AttachmentStorageProfile(backend="s3", s3_bucket="owned-private-test"), client=S3Client()
        ),
    ]
    for store in stores:
        with pytest.raises(ValueError):
            await store.put(key, b"bytes")


async def test_s3_failure_closes_stream_and_redacts_provider_details():
    from koinon.storage.s3 import S3BlobStore
    from koinon.storage.settings import AttachmentStorageProfile

    class FailingStream(BytesIO):
        def read(self, *args):
            raise RuntimeError("provider-private-diagnostic")

    client = S3Client()
    stream = FailingStream(b"bytes")
    client.get_object = lambda **kwargs: {"Body": stream, "ContentLength": 5}
    store = S3BlobStore(AttachmentStorageProfile(backend="s3", s3_bucket="owned-private-test"), client=client)
    with pytest.raises(OSError) as error:
        await store.get_bounded("namespace/file/original", 10)
    assert stream.closed and "provider-private-diagnostic" not in str(error.value)
