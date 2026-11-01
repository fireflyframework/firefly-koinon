# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from test_external_file_reviews import files as files
from test_external_file_reviews import manifest, ready_file, security


@pytest.fixture
async def queued(files):
    from koinon.assistants.entities import Provider
    from koinon.assistants.repositories import ProviderRepository
    from koinon.knowledge.bulk.service import FileBatches
    from koinon.knowledge.connections.entities import KnowledgeConnection
    from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository

    reviews, destination, context, store = files
    await context.get_bean(ProviderRepository).save(
        Provider(
            id="embedding-provider",
            tenant_id="north",
            name="Inert",
            kind="ollama",
            base_url="http://unresolved.invalid",
            model_ids=["embedding"],
            enabled=True,
            revision=1,
            validated_revision=1,
        )
    )
    await context.get_bean(KnowledgeConnectionRepository).save(
        KnowledgeConnection(
            id="embedding-connection",
            tenant_id="north",
            workspace_id=destination.workspace_id,
            scope_key=destination.workspace_id,
            domain="documents",
            role="documents.embedding",
            mode="provider",
            provider_id="embedding-provider",
            model_id="embedding",
            dimensions=768,
            embedding_fingerprint="f" * 64,
            created_by="issuer|owner",
            updated_by="issuer|owner",
        )
    )
    # Exercise the real large-file branch with a small fixture instead of allocating a large test payload.
    reviews.knowledge = SimpleNamespace(
        get=lambda: SimpleNamespace(settings=SimpleNamespace(max_upload_bytes=1))
    )
    return reviews, destination, context.get_bean(FileBatches), store


@pytest.mark.parametrize("reviewed", ["queued"], indirect=True)
async def test_explicit_approval_queues_pinned_original_and_one_source_without_full_read(queued, monkeypatch):
    reviews, destination, batches, store = queued
    with security():
        view, decision = await ready_file(reviews, destination)
        row = await reviews.rows.find_by_id(view.id)
        assert row.blob_reference_json and row.bulk_batch_id is None
        read = store.get_bounded

        async def never_read_whole_original(key, maximum):
            assert not key.endswith("/original")
            return await read(key, maximum)

        monkeypatch.setattr(store, "get_bounded", never_read_whole_original)
        result = await reviews.approve("issuer|owner", "north", view.id, decision, "approval")
        assert result.status == "ingesting" and result.source_id
        row = await reviews.rows.find_by_id(view.id)
        batch = await batches.get("issuer|owner", "north", row.bulk_batch_id)
        assert batch.status == "queued" and batch.total_items == 1
        item = (await batches.items("issuer|owner", "north", batch.id)).items[0]
        assert item.source_id == result.source_id and item.status == "queued"
        source = await reviews.authority.catalog.get("issuer|owner", "north", result.source_id)
        assert source.metadata_json["_koinon_external_review"]["review_id"] == view.id
        original = await batches.records.latest_upload(item.id)
        assert original.object_reference_json["sha256"] == view.sha256
        assert original.object_reference_json["store_identity"] != row.blob_reference_json["store_identity"]
        repeated = await reviews.approve("issuer|owner", "north", view.id, decision, "approval")
        assert repeated.source_id == result.source_id
        assert (await batches.items("issuer|owner", "north", batch.id)).total == 1


@pytest.mark.parametrize("reviewed", ["queued"], indirect=True)
async def test_replaced_sealed_object_does_not_submit_or_replay_approval(queued):
    reviews, destination, batches, store = queued
    with security():
        view, decision = await ready_file(reviews, destination)
        row = await reviews.rows.find_by_id(view.id)
        await store.put(row.blob_key, b"shared file content")
        result = await reviews.approve("issuer|owner", "north", view.id, decision, "approval")
        assert result.status == "unresolved" and result.receipt is None
        row = await reviews.rows.find_by_id(view.id)
        batch = await batches.get("issuer|owner", "north", row.bulk_batch_id)
        assert batch.status == "staging"
        repeated = await reviews.approve("issuer|owner", "north", view.id, decision, "approval")
        assert repeated.status == "unresolved" and repeated.source_id == result.source_id
        assert (await batches.items("issuer|owner", "north", batch.id)).items[0].job_id is None


@pytest.mark.parametrize("reviewed", ["queued"], indirect=True)
async def test_large_manifest_admission_requires_configured_queue_and_file_store(queued):
    from pyfly.kernel import InvalidRequestException

    reviews, destination, batches, _ = queued
    with security():
        large = {**manifest(destination), "size_bytes": 64 * 1024**2}
        view = await reviews.stage("issuer|owner", "north", large, "large")
        assert view.total_chunks == 1024
        batches.settings.max_file_bytes = 32 * 1024**2
        with pytest.raises(InvalidRequestException):
            await reviews.stage("issuer|owner", "north", large, "lower-bound")
