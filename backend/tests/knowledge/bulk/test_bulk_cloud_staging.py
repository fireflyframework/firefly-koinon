# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bulk uses the shared create-only SDK transport and retains profile identity."""

import importlib.util
from hashlib import sha256
from pathlib import Path

import pytest
from pyfly.core import Config
from pyfly.kernel import ConflictException

from koinon.knowledge.bulk.settings import BulkSettings
from koinon.knowledge.bulk.storage import BulkStorage
from koinon.storage.scratch import ScratchAdmission


@pytest.mark.parametrize("backend", ["azure", "gcs"])
async def test_two_independent_bulk_stores_read_same_immutable_object_without_shared_posix(backend):
    path = Path(__file__).resolve().parents[4] / "packages/storage/tests/test_cloud.py"
    spec = importlib.util.spec_from_file_location("bulk_sdk_protocol", path)
    protocol = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(protocol)
    client = protocol.AzureClient() if backend == "azure" else protocol.GcsClient()
    settings = BulkSettings(
        storage_backend=backend,
        azure_account_url="https://owned.blob.core.windows.net",
        azure_container="owned-private",
        azure_prefix="retained",
        gcs_bucket="owned-private",
        gcs_prefix="retained",
        storage_request_timeout_seconds=3,
    )
    first, second = (
        BulkStorage(settings, ScratchAdmission(Config({}))),
        BulkStorage(settings, ScratchAdmission(Config({}))),
    )
    first.configured().native._client = client
    second.configured().native._client = client
    await first.put("bulk/attempt.blob", b"original", sha256(b"original").hexdigest())
    assert (
        await second.read(
            "bulk/attempt.blob", 8, sha256(b"original").hexdigest(), storage_identity=first.identity()
        )
        == b"original"
    )
    with pytest.raises(OSError):
        await second.put("bulk/attempt.blob", b"changed!", sha256(b"changed!").hexdigest())
    assert client.objects["retained/bulk/attempt.blob"] == b"original"
    with pytest.raises(ConflictException) as moved:
        await second.read("bulk/attempt.blob", 8, sha256(b"original").hexdigest(), storage_identity="0" * 64)
    assert moved.value.code == "BULK_STORAGE_CHANGED"


async def test_local_attempt_is_create_only_and_cannot_replace_retained_bytes(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    storage = BulkStorage(BulkSettings(storage_root=str(root)), ScratchAdmission(Config({})))
    await storage.put("bulk/attempt.blob", b"original", sha256(b"original").hexdigest())
    with pytest.raises(OSError):
        await storage.put("bulk/attempt.blob", b"changed!", sha256(b"changed!").hexdigest())
    assert await storage.read("bulk/attempt.blob", 8, sha256(b"original").hexdigest()) == b"original"
