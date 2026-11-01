# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

from flycanon.config import CanonSettings
from flycanon.core.services.sources.async_ingest_service import AsyncIngestService
from flycanon.core.services.storage.local_fs import LocalFsObjectStore
from flycanon.interfaces.dtos.source import SubmitSourceRequest


def service(root):
    repository = SimpleNamespace(
        add=AsyncMock(side_effect=lambda row: row),
        append_event=AsyncMock(),
        mark_succeeded=AsyncMock(),
        mark_failed=AsyncMock(),
    )
    intake = SimpleNamespace(
        submit_file=AsyncMock(return_value=SimpleNamespace(id="source", n_chunks=1, content_sha256="a" * 64)),
        submit=AsyncMock(),
    )
    instance = AsyncIngestService(
        intake,
        repository,
        SimpleNamespace(record=AsyncMock()),
        None,
        CanonSettings(),
        object_store=LocalFsObjectStore(str(root)),
    )
    return instance, repository, intake


async def test_pending_jobs_store_only_scoped_immutable_reference_and_reuse_it(tmp_path):
    instance, repository, intake = service(tmp_path / "durable")
    row = await instance.submit_async(
        request=SubmitSourceRequest(),
        content=b"retained bytes",
        filename="retained.txt",
        content_type="text/plain",
        actor="owner",
        correlation_id=None,
        tenant_id="tenant",
        workspace_id="workspace",
    )
    assert "content_base64" not in row.metadata_json
    ref = row.metadata_json["content_reference"]
    assert ref["tenant_id"] == "tenant" and ref["workspace_id"] == "workspace"
    assert ref["object"]["size_bytes"] == 14
    await instance._process_claimed(row, 1)
    kwargs = intake.submit_file.await_args.kwargs
    assert kwargs["original_reference"].to_dict() == ref["object"]
    assert not kwargs["path"].exists()
    assert not intake.submit.called and not repository.mark_failed.called


async def test_changed_pending_reference_scope_fails_before_storage_or_intake(tmp_path):
    instance, repository, intake = service(tmp_path / "durable")
    row = await instance.submit_async(
        request=SubmitSourceRequest(),
        content=b"retained bytes",
        filename="retained.txt",
        content_type="text/plain",
        actor="owner",
        correlation_id=None,
        tenant_id="tenant",
        workspace_id="workspace",
    )
    row.metadata_json["content_reference"]["workspace_id"] = "another"
    await instance._process_claimed(row, 1)
    assert not intake.submit_file.called and repository.mark_failed.called


async def test_legacy_base64_jobs_remain_bounded_and_strict(tmp_path):
    instance, repository, intake = service(tmp_path / "durable")
    row = SimpleNamespace(
        id="old",
        metadata_json={"content_base64": "aGVsbG8="},
        tenant_id="tenant",
        workspace_id="workspace",
        filename="old.txt",
        content_type="text/plain",
        actor="owner",
        correlation_id=None,
        callback_url=None,
    )
    intake.submit.return_value = SimpleNamespace(id="source", n_chunks=1, content_sha256="a" * 64)
    await instance._process_claimed(row, 1)
    assert intake.submit.await_args.kwargs["content"] == b"hello"
    intake.submit.reset_mock()
    row.metadata_json = {"content_base64": "not valid!"}
    await instance._process_claimed(row, 1)
    assert not intake.submit.called and repository.mark_failed.called
