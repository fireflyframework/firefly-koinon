# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
from types import SimpleNamespace

import pytest


async def test_local_original_reads_are_bounded_before_loading_the_whole_object(tmp_path):
    from flycanon.core.services.storage.local_fs import LocalFsObjectStore
    from flycanon.core.services.storage.object_store import ObjectTooLargeError

    store = LocalFsObjectStore(str(tmp_path))
    await store.put("source", b"123456789")
    assert await store.get_bounded("source", 9) == b"123456789"
    with pytest.raises(ObjectTooLargeError):
        await store.get_bounded("source", 4)
    with pytest.raises(ValueError):
        await store.get_bounded("../foreign", 9)


async def test_s3_original_reads_cap_and_close_the_response_stream():
    from flycanon.core.services.storage.object_store import ObjectTooLargeError
    from flycanon.core.services.storage.s3 import S3ObjectStore

    stream = BytesIO(b"123456789")
    store = S3ObjectStore(
        "controlled", client=SimpleNamespace(get_object=lambda **kwargs: {"Body": stream}), owns_client=False
    )
    with pytest.raises(ObjectTooLargeError):
        await store.get_bounded("source", 4)
    assert stream.closed


async def test_opt_in_versioned_originals_do_not_overwrite_the_previous_object(tmp_path):
    from hashlib import sha256

    from flycanon.core.services.sources.intake_service import IntakeService
    from flycanon.core.services.storage.local_fs import LocalFsObjectStore
    from flycanon.models.entities.source import SourceRow

    store = LocalFsObjectStore(str(tmp_path))
    previous_key = "tenant/workspace/source.txt"
    await store.put(previous_key, b"previous original")
    service = object.__new__(IntakeService)
    service._object_store = store
    row = SourceRow(id="source", object_store_key=previous_key, metadata_json={})
    await service._store_original(
        source=row,
        content=b"next original",
        tenant_id="tenant",
        workspace_id="workspace",
        filename="source.txt",
        content_type="text/plain",
        versioned=True,
    )
    assert row.object_store_key != previous_key
    assert await store.get(previous_key) == b"previous original"
    assert await store.get(row.object_store_key) == b"next original"
    assert row.metadata_json["_persisted_original"] == {
        "sha256": sha256(b"next original").hexdigest(),
        "bytes": 13,
    }
