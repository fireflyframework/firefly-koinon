# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Parquet publication never coerces large artifacts into whole-object Python bytes."""

from pathlib import Path
from types import SimpleNamespace

import pytest


async def test_parse_large_file_uses_native_file_transport_without_read_bytes(tmp_path, monkeypatch):
    from flyquery.core.services.ingestion.stages.parse import _upload_parquet

    path = tmp_path / "artifact.parquet"
    with path.open("wb") as stream:
        stream.truncate(2 * 1024**2)
    seen = []

    async def create_file(key, source, content_type):
        seen.append((key, Path(source), content_type))

    def forbidden(*args, **kwargs):
        raise AssertionError("Whole-artifact read is forbidden")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    await _upload_parquet(SimpleNamespace(create_file=create_file), "artifact", str(path))
    assert seen == [("artifact", path, "application/octet-stream")]


async def test_legacy_store_large_file_rejected_before_loading_bytes(tmp_path):
    from flyquery.core.services.ingestion.resources import IngestionResourceLimitError
    from flyquery.core.services.ingestion.stages.parse import _upload_parquet

    path = tmp_path / "artifact.parquet"
    with path.open("wb") as stream:
        stream.truncate(1024**2 + 1)

    async def put(*args):
        raise AssertionError("Large legacy byte fallback is forbidden")

    with pytest.raises(IngestionResourceLimitError, match="file transport"):
        await _upload_parquet(SimpleNamespace(put=put), "artifact", str(path))


async def test_local_file_transport_idempotence_preserves_existing_artifact(tmp_path):
    from koinon_storage.cloud import ObjectIntegrityError

    from flyquery.core.services.storage.adapters.local_fs import LocalFsObjectStore

    store = LocalFsObjectStore(str(tmp_path / "store"))
    source = tmp_path / "source.parquet"
    source.write_bytes(b"original artifact")
    try:
        result = await store.create_file("table/v1.parquet", str(source), "application/octet-stream")
        assert result.size_bytes == len(b"original artifact")
        await store.create_file("table/v1.parquet", str(source), "application/octet-stream")
        source.write_bytes(b"different artifact")
        with pytest.raises(ObjectIntegrityError):
            await store.create_file("table/v1.parquet", str(source), "application/octet-stream")
        assert (tmp_path / "store/table/v1.parquet").read_bytes() == b"original artifact"
    finally:
        await store.close()
