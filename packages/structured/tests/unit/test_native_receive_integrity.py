# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


async def test_partial_low_level_write_cannot_truncate_the_parser_copy(monkeypatch):
    from flyquery.core.services.ingestion.stages import receive

    original_write = receive.os.write
    monkeypatch.setattr(receive.os, "write", lambda fd, data: original_write(fd, data[:7]))
    repository = SimpleNamespace(insert_received=AsyncMock())
    monkeypatch.setattr(receive, "FileRepository", lambda _: repository)
    data = b"item,amount\n" + b"A,47\n" * 100
    store = SimpleNamespace(put=AsyncMock())
    result = await receive.run_receive(
        tenant_id="owned",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        filename="orders.csv",
        file_bytes=data,
        actor="owner",
        object_store=store,
        session_factory=object(),
        settings=SimpleNamespace(max_file_mb=1, max_workspace_gb=1),
        workspace_storage_used_bytes=0,
    )
    try:
        copied = Path(result.local_temp_path).read_bytes()
        assert copied == data
        assert sha256(copied).hexdigest() == result.content_hash_sha256
        assert store.put.call_args.args[1] == copied
    finally:
        Path(result.local_temp_path).unlink()


def test_compressed_upload_parser_copy_retains_the_original_inner_format_suffix():
    from flyquery.core.services.ingestion.stages.receive import _pick_ext

    assert _pick_ext("orders.csv.gz", "csv", "gz") == ".csv.gz"
    assert _pick_ext("orders.csv.bz2", "csv", "bz2") == ".csv.bz2"
    assert _pick_ext("orders.csv.zip", "csv", "zip") == ".csv.zip"
