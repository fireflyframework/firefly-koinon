# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.knowledge.attachments.settings import AttachmentSettings
from koinon.knowledge.attachments.storage import AttachmentStorage


def record(content):
    return SimpleNamespace(
        id=str(uuid4()),
        tenant_id="tenant",
        subject="issuer|owner",
        thread_id="thread",
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
    )


async def test_private_atomic_storage_roundtrip_and_original_digest_fence(tmp_path):
    storage = AttachmentStorage(AttachmentSettings(storage_root=str(tmp_path / "private")))
    content = b"Private original bytes"
    row = record(content)
    await storage.put(row, content)
    assert await storage.read(row) == content
    assert storage.settings.storage_root not in storage.key(row)
    assert (tmp_path / "private").stat().st_mode & 0o077 == 0
    await storage.configured().put(storage.key(row), b"Different bytes")
    with pytest.raises(ConflictException) as error:
        await storage.read(row)
    assert error.value.code == "ATTACHMENT_DIGEST_MISMATCH"


def test_unconfigured_or_public_directory_never_becomes_an_implicit_private_store(tmp_path):
    with pytest.raises(ServiceUnavailableException):
        AttachmentStorage(AttachmentSettings()).configured()
    directory = tmp_path / "public"
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)
    with pytest.raises(ServiceUnavailableException):
        AttachmentStorage(AttachmentSettings(storage_root=str(directory))).configured()
    assert directory.stat().st_mode & 0o777 == 0o755


def test_cached_store_rechecks_directory_privacy_before_each_use(tmp_path):
    directory = tmp_path / "private"
    storage = AttachmentStorage(AttachmentSettings(storage_root=str(directory)))
    storage.configured()
    directory.chmod(0o755)
    with pytest.raises(ServiceUnavailableException):
        storage.configured()


def test_private_read_only_directory_is_not_reported_as_writable_storage(tmp_path):
    directory = tmp_path / "read-only"
    directory.mkdir(mode=0o500)
    try:
        with pytest.raises(ServiceUnavailableException):
            AttachmentStorage(AttachmentSettings(storage_root=str(directory))).configured()
    finally:
        directory.chmod(0o700)
