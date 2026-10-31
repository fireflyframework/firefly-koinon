# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
from types import SimpleNamespace

import pytest
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder


def security(token="origin"):
    return SecurityContextHolder.using(
        SecurityContext(
            user_id="owner", attributes={"iss": "issuer", "sub": "owner", "koinon_token_id": token}
        )
    )


@pytest.fixture
async def files(reviewed, tmp_path):
    from koinon.knowledge.external_reviews.file_service import ExternalFileReviews
    from koinon.storage.local import LocalBlobStore

    _, _, destination, context = reviewed
    root = tmp_path / "objects"
    root.mkdir(mode=0o700)
    service = context.get_bean(ExternalFileReviews)
    store = LocalBlobStore(str(root))
    service.storage.attachments = SimpleNamespace(
        get=lambda: SimpleNamespace(
            configured=lambda: store, profile=SimpleNamespace(max_object_bytes=64 * 1024 * 1024)
        )
    )
    service.knowledge = SimpleNamespace(
        get=lambda: SimpleNamespace(settings=SimpleNamespace(max_upload_bytes=32 * 1024 * 1024))
    )
    return service, destination, context, store


def manifest(destination, content=b"shared file content"):
    return {
        "filename": "evidence.txt",
        "content_type": "text/plain",
        "mode": "document",
        "destination_id": destination.id,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def chunk(content, index=0):
    return {
        "index": index,
        "data_base64": base64.b64encode(content).decode(),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


async def test_file_staging_uses_configured_durable_bytes_and_exact_full_hash_before_review(files):
    service, destination, _, store = files
    content = b"a" * 65536 + b"tail"
    with security():
        view = await service.stage("issuer|owner", "north", manifest(destination, content), "file-stage")
        assert view.status == "uploading" and view.total_chunks == 2
        assert "nonce" not in view.model_dump_json()
        await service.chunk("issuer|owner", "north", view.id, chunk(content[65536:], 1))
        await service.chunk("issuer|owner", "north", view.id, chunk(content[:65536]))
        assert (
            await service.chunk("issuer|owner", "north", view.id, chunk(content[:65536]))
        ).received_chunks == 2
        sealed = await service.seal("issuer|owner", "north", view.id)
        assert sealed.status == "preview" and sealed.sha256 == hashlib.sha256(content).hexdigest()
        challenge = await service.challenge("issuer|owner", "north", view.id)
    row = await service.rows.find_by_id(view.id)
    assert await store.get_bounded(row.blob_key, len(content)) == content
    assert challenge.nonce not in str(row.__dict__) and row.nonce_sha256


@pytest.mark.parametrize("wrong", ["index", "length", "hash", "base64", "oversize"])
async def test_invalid_chunk_cannot_change_or_complete_staged_file(files, wrong):
    from pydantic import ValidationError
    from pyfly.kernel import ConflictException, InvalidRequestException

    service, destination, _, _ = files
    with security():
        view = await service.stage("issuer|owner", "north", manifest(destination), "file-stage")
        values = chunk(b"shared file content")
        if wrong == "index":
            values["index"] = 1
        if wrong == "length":
            values = chunk(b"short")
        if wrong == "hash":
            values["sha256"] = "a" * 64
        if wrong == "base64":
            values["data_base64"] = "invalid!"
        if wrong == "oversize":
            values["data_base64"] = "a" * 87385
        with pytest.raises((ValidationError, ConflictException, InvalidRequestException)):
            await service.chunk("issuer|owner", "north", view.id, values)
        assert (await service.get("issuer|owner", "north", view.id)).received_chunks == 0


async def test_missing_or_conflicting_chunk_and_full_digest_mismatch_never_offer_approval(files):
    from pyfly.kernel import ConflictException

    service, destination, _, _ = files
    with security():
        view = await service.stage("issuer|owner", "north", manifest(destination), "file-stage")
        with pytest.raises(ConflictException):
            await service.seal("issuer|owner", "north", view.id)
        challenge = await service.challenge("issuer|owner", "north", view.id)
        assert challenge.review.status == "uploading"
        with pytest.raises(ConflictException):
            await service.approve(
                "issuer|owner",
                "north",
                view.id,
                {
                    "expected_revision": view.revision,
                    "authorization_digest": view.authorization_digest,
                    "nonce": challenge.nonce,
                },
                "approve",
            )
        await service.chunk("issuer|owner", "north", view.id, chunk(b"shared file content"))
        with pytest.raises(ConflictException):
            await service.chunk("issuer|owner", "north", view.id, chunk(b"changed file words!"))
        other = await service.stage(
            "issuer|owner", "north", {**manifest(destination), "sha256": "f" * 64}, "other"
        )
        await service.chunk("issuer|owner", "north", other.id, chunk(b"shared file content"))
        with pytest.raises(ConflictException):
            await service.seal("issuer|owner", "north", other.id)


@pytest.fixture
async def ingestion(files):
    from koinon.catalog.service import CatalogService
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings

    service, destination, context, store = files

    class Domains:
        calls = []
        fail = False

        async def ensure_workspace(self, **values):
            return "native-space"

        async def ingest_document(self, **values):
            await values["authorize_commit"]()
            self.calls.append(values)
            if self.fail:
                raise RuntimeError("Owned simulated native intake failure")
            return {"source_id": "native-document", "chunk_count": 1}

        async def ingest_dataset(self, **values):
            self.calls.append(values)
            if self.fail:
                raise RuntimeError("Owned simulated native intake failure")
            return {"file_id": "native-file", "dataset_id": "native-dataset", "tables": []}

    domains = Domains()
    facade = KnowledgeFacade(
        context.get_bean(CatalogService),
        context.get_bean(DomainBindingRepository),
        domains,
        KnowledgeSettings(),
    )
    service.knowledge = SimpleNamespace(get=lambda: facade)
    return service, destination, context, domains, facade


async def ready_file(service, destination, *, mode="document"):
    content = b"shared file content"
    view = await service.stage("issuer|owner", "north", {**manifest(destination), "mode": mode}, "file-stage")
    await service.chunk("issuer|owner", "north", view.id, chunk(content))
    await service.seal("issuer|owner", "north", view.id)
    challenge = await service.challenge("issuer|owner", "north", view.id)
    decision = {
        "expected_revision": view.revision,
        "authorization_digest": view.authorization_digest,
        "nonce": challenge.nonce,
    }
    return view, decision


@pytest.mark.parametrize("mode", ["document", "dataset"])
async def test_approved_original_uses_actual_canonical_facade_and_typed_receipt_once(ingestion, mode):
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import InvalidHierarchy

    service, destination, _, domains, facade = ingestion
    with security():
        view, decision = await ready_file(service, destination, mode=mode)
        assert not domains.calls
        result = await service.approve("issuer|owner", "north", view.id, decision, "approve")
        assert result.status == "committed" and result.receipt.source.id == result.source_id
        assert result.receipt.assets[0].kind == mode and result.receipt.source.metadata["bytes"] == 19
        assert result.tenant_id == "north" and result.authority == "unverified"
        assert domains.calls[0]["content"] == b"shared file content"
        assert (
            await service.approve("issuer|owner", "north", view.id, decision, "approve")
        ).receipt == result.receipt
        with pytest.raises(ConflictException):
            await service.approve("issuer|owner", "north", view.id, decision, "another-key")
        source = await facade.catalog.get("issuer|owner", "north", result.source_id)
        assert source.metadata_json["_koinon_external_review"]["review_id"] == view.id
        with pytest.raises(InvalidHierarchy):
            await facade.catalog.update(
                "issuer|owner",
                "north",
                source.id,
                {"metadata": {"_koinon_external_review": {"review_id": "forged"}}},
            )
        updated = await facade.catalog.update(
            "issuer|owner", "north", source.id, {"metadata": {"note": "editable"}}
        )
        assert updated.metadata_json["_koinon_external_review"]["review_id"] == view.id
        with pytest.raises(ConflictException):
            await facade.catalog.delete("issuer|owner", "north", source.id)
    assert len(domains.calls) == 1


async def test_native_failure_retains_actual_source_and_never_replays_consumed_approval(ingestion):
    service, destination, _, domains, _ = ingestion
    domains.fail = True
    with security():
        view, decision = await ready_file(service, destination)
        result = await service.approve("issuer|owner", "north", view.id, decision, "approve")
        assert result.status == "unresolved" and result.source_id and result.intake_status == "error"
        assert result.receipt is None
        assert (
            await service.approve("issuer|owner", "north", view.id, decision, "approve")
        ).status == "unresolved"
    assert len(domains.calls) == 1


async def test_ambiguous_failure_before_source_callback_never_starts_a_second_upload(ingestion):
    service, destination, _, _, facade = ingestion
    calls = []

    async def broken(*args, **kwargs):
        calls.append(True)
        raise RuntimeError("Owned simulated interruption before source observation")

    facade.upload = broken
    with security():
        view, decision = await ready_file(service, destination)
        result = await service.approve("issuer|owner", "north", view.id, decision, "approve")
        assert result.status == "unresolved" and result.source_id is None and result.receipt is None
        assert (
            await service.approve("issuer|owner", "north", view.id, decision, "approve")
        ).status == "unresolved"
    assert calls == [True]


async def test_receipt_interruption_reconciles_only_recorded_source_and_native_bindings(
    ingestion, monkeypatch
):
    service, destination, _, domains, _ = ingestion
    original = service.finish
    disrupted = []

    async def interrupt(subject, tenant, identifier, result=None):
        if result is not None and not disrupted:
            disrupted.append(True)
            raise RuntimeError("Owned interruption after canonical return before receipt")
        return await original(subject, tenant, identifier, result)

    monkeypatch.setattr(service, "finish", interrupt)
    with security():
        view, decision = await ready_file(service, destination)
        result = await service.approve("issuer|owner", "north", view.id, decision, "approve")
        assert result.status == "committed" and result.receipt and result.source_id
    assert len(domains.calls) == 1 and disrupted == [True]


async def test_file_boundaries_cancel_incomplete_upload_and_deny_changed_credential(files):
    from datetime import UTC, datetime, timedelta

    from pydantic import ValidationError
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import AccessDenied

    service, destination, _, _ = files
    with security():
        with pytest.raises(ValidationError):
            await service.stage(
                "issuer|owner", "north", {**manifest(destination), "size_bytes": 33554433}, "large"
            )
        view = await service.stage("issuer|owner", "north", manifest(destination), "file-stage")
        challenge = await service.challenge("issuer|owner", "north", view.id)
    with security("other"), pytest.raises(AccessDenied):
        await service.chunk("issuer|owner", "north", view.id, chunk(b"shared file content"))
    decision = {
        "expected_revision": view.revision,
        "authorization_digest": view.authorization_digest,
        "nonce": challenge.nonce,
    }
    with security():
        assert (await service.cancel("issuer|owner", "north", view.id, decision)).status == "cancelled"
        assert (await service.cancel("issuer|owner", "north", view.id, decision)).status == "cancelled"
        with pytest.raises(ConflictException):
            await service.approve("issuer|owner", "north", view.id, decision, "approve")
        expired = await service.stage("issuer|owner", "north", manifest(destination), "expired")
        row = await service.rows.find_by_id(expired.id)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await service.rows.save(row)
        with pytest.raises(ConflictException):
            await service.chunk("issuer|owner", "north", expired.id, chunk(b"shared file content"))


async def test_pending_file_quota_counts_announced_bytes_under_owner_admission_lease(files):
    from pyfly.kernel import ConflictException

    service, destination, _, _ = files
    with security():
        for index in range(8):
            await service.stage("issuer|owner", "north", manifest(destination), f"file-{index}")
        with pytest.raises(ConflictException) as failure:
            await service.stage("issuer|owner", "north", manifest(destination), "file-9")
        assert failure.value.code == "EXTERNAL_STAGING_LIMIT"


@pytest.mark.parametrize("backend", ["azure", "gcs", "s3"])
async def test_file_staging_through_real_cloud_blob_port_with_owned_sdk_double(files, backend):
    import importlib.util
    from pathlib import Path

    from koinon.storage.cloud import CloudBlobStore
    from koinon.storage.s3 import S3BlobStore
    from koinon.storage.settings import AttachmentStorageProfile

    service, destination, _, _ = files
    path = (
        Path(__file__).resolve().parents[2] / "storage/test_private_blobs.py"
        if backend == "s3"
        else Path(__file__).resolve().parents[4] / "packages/storage/tests/test_cloud.py"
    )
    spec = importlib.util.spec_from_file_location("owned_cloud_protocol_fixture", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    client = (
        helper.S3Client()
        if backend == "s3"
        else helper.AzureClient()
        if backend == "azure"
        else helper.GcsClient()
    )
    profile = AttachmentStorageProfile(
        backend=backend,
        azure_account_url="https://owned.blob.core.windows.net",
        azure_container="owned-private",
        gcs_bucket="owned-private",
        s3_bucket="owned-private",
        request_timeout_seconds=3,
    )
    store = S3BlobStore(profile, client=client) if backend == "s3" else CloudBlobStore(profile, client=client)
    service.storage.attachments = SimpleNamespace(
        get=lambda: SimpleNamespace(configured=lambda: store, profile=profile)
    )
    with security():
        view = await service.stage("issuer|owner", "north", manifest(destination), "cloud-file")
        await service.chunk("issuer|owner", "north", view.id, chunk(b"shared file content"))
        sealed = await service.seal("issuer|owner", "north", view.id)
        assert sealed.status == "preview"
    assert set(client.objects.values()) == {b"shared file content"}
    assert len(client.objects) == 2


async def test_expired_unpurged_files_and_rotated_credentials_do_not_reset_owner_quota(files):
    from datetime import UTC, datetime, timedelta

    from pyfly.kernel import ConflictException

    service, destination, _, _ = files
    with security():
        for index in range(8):
            view = await service.stage("issuer|owner", "north", manifest(destination), f"file-{index}")
            row = await service.rows.find_by_id(view.id)
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await service.rows.save(row)
    with security("other"), pytest.raises(ConflictException) as failure:
        await service.stage("issuer|owner", "north", manifest(destination), "cross-credential")
    assert failure.value.code == "EXTERNAL_STAGING_LIMIT"


async def test_gc_only_expired_never_intake_keys_has_durable_bounded_cursor(files):
    from datetime import UTC, datetime, timedelta

    from pyfly.kernel import ConflictException

    from koinon.catalog.repositories import MembershipRepository

    service, destination, context, store = files
    owner = await context.get_bean(MembershipRepository).find_by_id("owner")
    owner.role = "admin"
    await context.get_bean(MembershipRepository).save(owner)
    with security():
        view = await service.stage("issuer|owner", "north", manifest(destination), "file-stage")
        await service.chunk("issuer|owner", "north", view.id, chunk(b"shared file content"))
        await service.seal("issuer|owner", "north", view.id)
    # Cleanup is an explicit interactive admin operation, not approval through the originating PAT.
    with SecurityContextHolder.using(
        SecurityContext(user_id="owner", attributes={"iss": "issuer", "sub": "owner"})
    ):
        with pytest.raises(ConflictException):
            await service.cleanup("issuer|owner", "north", {"review_ids": [view.id], "max_objects": 1})
        row = await service.rows.find_by_id(view.id)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await service.rows.save(row)
        first = await service.cleanup("issuer|owner", "north", {"review_ids": [view.id], "max_objects": 1})
        assert first.reviews[0].status == "purging" and first.reviews[0].processed_objects == 1
        row = await service.rows.find_by_id(view.id)
        assert row.gc_cursor == 1 and row.status == "cancelled"
        second = await service.cleanup("issuer|owner", "north", {"review_ids": [view.id], "max_objects": 1})
        assert second.reviews[0].status == "purged" and second.reviews[0].processed_objects == 2
        assert (await service.rows.find_by_id(view.id)).gc_status == "purged"
    with pytest.raises(FileNotFoundError):
        await store.get_bounded(row.blob_key, 19)


@pytest.mark.parametrize("uncertain", [False, True])
async def test_gc_refuses_unresolved_or_committed_ingestion_evidence(ingestion, uncertain):
    from pyfly.kernel import ConflictException

    from koinon.catalog.repositories import MembershipRepository

    service, destination, context, domains, _ = ingestion
    domains.fail = uncertain
    with security():
        view, decision = await ready_file(service, destination)
        result = await service.approve("issuer|owner", "north", view.id, decision, "approve")
        assert result.status == ("unresolved" if uncertain else "committed")
    owner = await context.get_bean(MembershipRepository).find_by_id("owner")
    owner.role = "admin"
    await context.get_bean(MembershipRepository).save(owner)
    with (
        SecurityContextHolder.using(
            SecurityContext(user_id="owner", attributes={"iss": "issuer", "sub": "owner"})
        ),
        pytest.raises(ConflictException),
    ):
        await service.cleanup("issuer|owner", "north", {"review_ids": [view.id]})
    row = await service.rows.find_by_id(view.id)
    assert (
        await service.storage.read(row, "original", 19, row.request_json["sha256"]) == b"shared file content"
    )


async def test_gc_interruption_keeps_quota_until_same_owned_cursor_is_completed(files, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from pyfly.kernel import ConflictException, ServiceUnavailableException

    from koinon.catalog.repositories import MembershipRepository

    service, destination, context, store = files
    service.settings.max_active_files = 1
    owner = await context.get_bean(MembershipRepository).find_by_id("owner")
    owner.role = "admin"
    await context.get_bean(MembershipRepository).save(owner)
    with security():
        view = await service.stage("issuer|owner", "north", manifest(destination), "file-stage")
        await service.chunk("issuer|owner", "north", view.id, chunk(b"shared file content"))
        await service.seal("issuer|owner", "north", view.id)
    row = await service.rows.find_by_id(view.id)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await service.rows.save(row)
    original, failures = store.delete, []

    async def interrupted(key):
        await original(key)
        if not failures:
            failures.append(key)
            raise OSError("Owned ambiguous deletion response")

    monkeypatch.setattr(store, "delete", interrupted)
    with SecurityContextHolder.using(
        SecurityContext(user_id="owner", attributes={"iss": "issuer", "sub": "owner"})
    ):
        with pytest.raises(ServiceUnavailableException):
            await service.cleanup("issuer|owner", "north", {"review_ids": [view.id]})
        current = await service.rows.find_by_id(view.id)
        assert current.gc_cursor == 0 and current.gc_status == "purging"
        with security(), pytest.raises(ConflictException):
            await service.stage("issuer|owner", "north", manifest(destination), "not-released")
        result = await service.cleanup("issuer|owner", "north", {"review_ids": [view.id]})
        assert result.reviews[0].status == "purged"
        repeated = await service.cleanup("issuer|owner", "north", {"review_ids": [view.id]})
        assert repeated == result
    assert len(failures) == 1
    with security():
        assert (
            await service.stage("issuer|owner", "north", manifest(destination), "released")
        ).status == "uploading"


async def test_announced_byte_quota_can_be_lower_than_per_file_limit(files):
    from pyfly.kernel import ConflictException

    service, destination, _, _ = files
    service.settings.max_staged_bytes = 19
    with security():
        await service.stage("issuer|owner", "north", manifest(destination), "one")
        with pytest.raises(ConflictException) as failure:
            await service.stage("issuer|owner", "north", manifest(destination), "two")
    assert failure.value.code == "EXTERNAL_STAGING_LIMIT"
