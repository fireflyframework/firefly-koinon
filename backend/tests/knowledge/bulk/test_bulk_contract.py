# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError

from koinon.knowledge.bulk.dtos import FileBatchCreate, aggregate_status


def manifest():
    return {
        "destination": {"workspace_id": "workspace", "project_id": "project", "parent_id": "collection"},
        "items": [
            {
                "client_item_id": "one",
                "filename": "facts.md",
                "mode": "document",
                "size_bytes": 4,
                "sha256": "a" * 64,
            }
        ],
    }


def test_manifest_is_bounded_portable_and_rejects_path_or_duplicate_client_identity():
    assert FileBatchCreate.model_validate(manifest()).items[0].filename == "facts.md"
    for key, value in [
        ("filename", "../secret"),
        ("size_bytes", True),
        ("size_bytes", 134217729),
        ("sha256", "nope"),
        ("mode", "curated"),
    ]:
        data = manifest()
        data["items"][0][key] = value
        with pytest.raises(ValidationError):
            FileBatchCreate.model_validate(data)
    data = manifest()
    data["items"] *= 2
    with pytest.raises(ValidationError):
        FileBatchCreate.model_validate(data)
    data = manifest()
    data["destination"]["object_store_key"] = "private"
    with pytest.raises(ValidationError):
        FileBatchCreate.model_validate(data)


def test_aggregate_status_never_relabels_published_success_as_cancelled_or_hides_uncertainty():
    assert aggregate_status(["succeeded", "cancelled"]) == "partial"
    assert aggregate_status(["succeeded", "failed"]) == "partial"
    assert aggregate_status(["reconciling", "succeeded"]) == "reconciling"
    assert aggregate_status(["running", "queued"]) == "running"
    assert aggregate_status(["succeeded", "succeeded"]) == "succeeded"
    assert aggregate_status(["cancelled", "cancelled"]) == "cancelled"
    assert aggregate_status(["awaiting_upload", "staged"]) == "staging"


def test_capabilities_explicitly_bound_local_staging_to_one_shared_host_lock_namespace():
    from koinon.knowledge.bulk.dtos import FileBatchCapabilities

    value = FileBatchCapabilities(
        configured=False,
        modes=[],
        max_files=100,
        max_file_bytes=33554432,
        max_batch_bytes=268435456,
        max_active_batches_per_subject=2,
    )
    assert value.staging_topology == "single_host_shared_durable_posix"
    assert value.writer_fence == "primary_database_generation_lease"
    assert value.automatic_unknown_replay is False
    with pytest.raises(ValidationError):
        FileBatchCapabilities.model_validate({**value.model_dump(), "staging_topology": "ephemeral_replicas"})
