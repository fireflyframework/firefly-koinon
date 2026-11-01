# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace

import pytest
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.kernel import ConflictException

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.jobs.service import JobService
from koinon.knowledge.bulk.dtos import BulkAction, FileBatchCreate
from koinon.knowledge.bulk.service import FileBatches


@pytest.fixture
async def bulk(tmp_path, request):
    try:
        bulk_url = request.getfixturevalue("bulk_url")
    except pytest.FixtureLookupError:
        bulk_url = f"sqlite+aiosqlite:///{tmp_path / 'bulk.db'}"
    (tmp_path / "private").mkdir(mode=0o700)
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": bulk_url,
                        }
                    },
                },
                "koinon": {
                    "knowledge": {
                        "bulk": {"storage_root": str(tmp_path / "private"), "max_local_storage_operations": 8}
                    }
                },
            }
        )
    )
    for package in ["koinon.catalog", "koinon.jobs", "koinon.storage", "koinon.knowledge.bulk"]:
        scan_package(package, context.container)
    from koinon.assistants.repositories import ProviderRepository
    from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.tokens.authorization import TokenRestriction
    from koinon.tokens.repositories import PersonalTokenRepository

    context.register_bean(PersonalTokenRepository)
    context.register_bean(TokenRestriction)
    context.register_bean(ProviderRepository)
    context.register_bean(KnowledgeConnectionRepository)
    context.register_bean(DomainBindingRepository)
    await context.start()
    try:
        await context.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        members = context.get_bean(MembershipRepository)
        await members.save(Membership(id="editor", subject="issuer|editor", tenant_id="north", role="editor"))
        catalog = context.get_bean(CatalogService)
        workspace = await catalog.create("issuer|editor", "north", kind="workspace", name="Workspace")
        project = await catalog.create(
            "issuer|editor", "north", kind="project", name="Project", parent_id=workspace.id
        )
        parent = await catalog.create(
            "issuer|editor", "north", kind="collection", name="Collection", parent_id=project.id
        )
        from koinon.assistants.entities import Provider
        from koinon.knowledge.connections.entities import KnowledgeConnection

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
                workspace_id=workspace.id,
                scope_key=workspace.id,
                domain="documents",
                role="documents.embedding",
                mode="provider",
                provider_id="embedding-provider",
                model_id="embedding",
                dimensions=768,
                embedding_fingerprint="f" * 64,
                created_by="issuer|editor",
                updated_by="issuer|editor",
            )
        )
        yield SimpleNamespace(
            service=context.get_bean(FileBatches),
            context=context,
            catalog=catalog,
            members=members,
            target={"workspace_id": workspace.id, "project_id": project.id, "parent_id": parent.id},
        )
    finally:
        await context.stop()


def request(target, content=b"original"):
    return FileBatchCreate.model_validate(
        {
            "destination": target,
            "items": [
                {
                    "client_item_id": "one",
                    "filename": "facts.md",
                    "mode": "document",
                    "size_bytes": len(content),
                    "sha256": sha256(content).hexdigest(),
                }
            ],
        }
    )


async def test_create_and_stage_replay_survive_new_service_instance_without_duplicate_catalog(bulk):
    a = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create-key")
    replay = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create-key")
    assert replay.id == a.id and a.status == "staging"
    items = await bulk.service.items("issuer|editor", "north", a.id)
    original = await bulk.service.stage(
        "issuer|editor", "north", a.id, items.items[0].id, b"original", "upload-key"
    )
    assert original.sha256 == sha256(b"original").hexdigest()
    from koinon.knowledge.bulk.storage import BulkStorage

    previous = bulk.service
    bulk.service = FileBatches(
        previous.catalog,
        previous.records,
        BulkStorage(previous.settings, previous.storage.scratch),
        previous.settings,
        previous.jobs,
        previous.authority,
        previous.intakes,
    )
    assert (
        await bulk.service.create("issuer|editor", "north", request(bulk.target), "create-key")
    ).id == a.id
    same = await bulk.service.stage(
        "issuer|editor", "north", a.id, items.items[0].id, b"original", "upload-key"
    )
    assert same.receipt_id == original.receipt_id
    assert (await bulk.service.get("issuer|editor", "north", a.id)).counts["staged"] == 1
    assert len(await bulk.catalog.list("issuer|editor", "north", kind="source")) == 1
    assert len(await bulk.catalog.list("issuer|editor", "north", kind="document")) == 1
    with pytest.raises(ConflictException):
        await bulk.service.create("issuer|editor", "north", request(bulk.target, b"different"), "create-key")


async def test_submission_is_idempotent_and_revision_checked_before_any_job_then_cancel_preserves_original(
    bulk,
):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create-key")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    with pytest.raises(ConflictException):
        await bulk.service.submit(
            "issuer|editor", "north", batch.id, BulkAction(expected_revision=batch.revision), "submit"
        )
    await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    current = await bulk.service.get("issuer|editor", "north", batch.id)
    queued = await bulk.service.submit(
        "issuer|editor", "north", batch.id, BulkAction(expected_revision=current.revision), "submit"
    )
    assert queued.status == "queued"
    assert (
        await bulk.service.submit(
            "issuer|editor", "north", batch.id, BulkAction(expected_revision=current.revision), "submit"
        )
    ).id == batch.id
    assert len(await bulk.context.get_bean(JobService).repository.find_all(tenant_id="north")) == 1
    cancelled = await bulk.service.cancel(
        "issuer|editor", "north", batch.id, BulkAction(expected_revision=queued.revision), "cancel"
    )
    assert cancelled.status == "cancelled"
    receipt = await bulk.service.receipt("issuer|editor", "north", batch.id, item.id)
    assert receipt.sha256 == sha256(b"original").hexdigest()
    replay = await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    assert replay.receipt_id == receipt.receipt_id


async def test_revoked_membership_during_blob_io_cannot_publish_original_winner_or_release_foreign_work(bulk):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.bulk.repositories import BulkRepository

    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    original = bulk.service.storage.put

    async def store_then_revoke(*args):
        await original(*args)
        member = await bulk.members.find_by_id("editor")
        member.active = False
        await bulk.members.save(member)

    bulk.service.storage.put = store_then_revoke
    with pytest.raises(AccessDenied):
        await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        preserved = await records.item(batch.id, item.id)
        assert preserved.winning_upload_id is None and preserved.status == "awaiting_upload"
        assert (await records.quota("tenant:north")).active_uploads == 0
        assert (await records.quota("global:uploads")).active_uploads == 0


async def test_pat_current_scope_role_intersection_and_originating_credential_are_preserved(bulk):
    from datetime import timedelta

    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.bulk.entities import now
    from koinon.tokens.entities import PersonalToken
    from koinon.tokens.repositories import PersonalTokenRepository

    repo = bulk.context.get_bean(PersonalTokenRepository)
    token = PersonalToken(
        id="pat-origin",
        subject="issuer|editor",
        tenant_id="north",
        name="Inert",
        token_hash="f" * 64,
        prefix="test",
        scopes=["catalog:read", "catalog:write", "ingest:write"],
        workspace_ids=[bulk.target["workspace_id"]],
        asset_ids=[bulk.target["parent_id"]],
        resource_ids=[bulk.target["workspace_id"], bulk.target["project_id"]],
        expires_at=now() + timedelta(hours=1),
    )
    await repo.save(token)
    with SecurityContextHolder.using(
        SecurityContext(user_id="issuer|editor", attributes={"koinon_token_id": token.id})
    ):
        batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "pat-key")
        assert (await bulk.service.get("issuer|editor", "north", batch.id)).id == batch.id
        token.scopes = ["catalog:read"]
        await repo.save(token)
        with pytest.raises(AccessDenied):
            await bulk.service.submit(
                "issuer|editor", "north", batch.id, BulkAction(expected_revision=batch.revision), "submit"
            )
        token.scopes = ["catalog:read", "catalog:write", "ingest:write"]
        token.revoked_at = now()
        await repo.save(token)
        with pytest.raises(AccessDenied):
            await bulk.service.get("issuer|editor", "north", batch.id)
    with pytest.raises(AccessDenied):
        await bulk.service.get("issuer|editor", "north", batch.id)


async def test_raw_stream_permit_precedes_request_body_and_replayer_never_releases_writer_permit(bulk):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.knowledge.bulk.repositories import BulkRepository

    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    replayer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    assert writer.write is True and replayer.write is False and writer.upload_id == replayer.upload_id
    await bulk.service.abort_stream("north", replayer)
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        quota = await bulk.context.get_bean(BulkRepository).quota("tenant:north")
        assert quota.active_uploads == 1
    result = await bulk.service.finish_stream(
        "issuer|editor",
        "north",
        batch.id,
        item.id,
        writer,
        b"original",
        len(b"original"),
        sha256(b"original").hexdigest(),
    )
    assert result.receipt_id == writer.upload_id


async def test_batch_pages_count_only_current_owner_and_current_workspace_visibility(bulk):
    first = await bulk.service.create("issuer|editor", "north", request(bulk.target), "one")
    workspace = await bulk.catalog.create("issuer|editor", "north", kind="workspace", name="Other")
    project = await bulk.catalog.create(
        "issuer|editor", "north", kind="project", name="Other", parent_id=workspace.id
    )
    parent = await bulk.catalog.create(
        "issuer|editor", "north", kind="collection", name="Other", parent_id=project.id
    )
    target = {"workspace_id": workspace.id, "project_id": project.id, "parent_id": parent.id}
    await bulk.service.create("issuer|editor", "north", request(target), "two")
    page = await bulk.service.list("issuer|editor", "north", page=1, page_size=1)
    assert len(page.items) == 1 and page.total == 2 and page.pages == 2
    member = await bulk.members.find_by_id("editor")
    member.workspace_id = bulk.target["workspace_id"]
    await bulk.members.save(member)
    page = await bulk.service.list("issuer|editor", "north", page=1, page_size=1)
    assert [x.id for x in page.items] == [first.id] and page.total == 1 and page.pages == 1
    beyond = await bulk.service.list("issuer|editor", "north", page=2, page_size=1)
    assert beyond.items == [] and beyond.total == 1


async def test_tiny_manifests_cannot_bypass_active_or_retained_metadata_admission_bounds(bulk):
    from pyfly.kernel import RateLimitException

    bulk.service.settings.max_active_batches_per_subject = 1
    first = await bulk.service.create("issuer|editor", "north", request(bulk.target), "capacity-first")
    with pytest.raises(RateLimitException) as blocked:
        await bulk.service.create("issuer|editor", "north", request(bulk.target), "capacity-second")
    assert blocked.value.code == "BULK_BATCH_LIMIT"
    await bulk.service.cancel(
        "issuer|editor", "north", first.id, BulkAction(expected_revision=first.revision), "cancel-first"
    )
    bulk.service.settings.max_batches_per_tenant = 1
    with pytest.raises(RateLimitException) as history:
        await bulk.service.create("issuer|editor", "north", request(bulk.target), "capacity-history")
    assert history.value.code == "BULK_HISTORY_LIMIT"
    assert (
        await bulk.service.create("issuer|editor", "north", request(bulk.target), "capacity-first")
    ).id == first.id


async def test_upload_recovery_fences_expired_database_writer_and_never_replays_bytes(bulk):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "recover-create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    ticket = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "interrupted")
    with pytest.raises(ConflictException) as active:
        await bulk.service.recover_original(
            "issuer|editor",
            "north",
            batch.id,
            item.id,
            BulkAction(expected_revision=batch.revision),
            "recover",
        )
    assert active.value.code == "BULK_UPLOAD_ACTIVE"
    from datetime import UTC, datetime

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    from koinon.knowledge.bulk.entities import BulkUploadState

    async with bulk.context.get_bean(DataSourceRegistry).get("primary").engine.begin() as connection:
        await connection.execute(
            update(BulkUploadState)
            .where(BulkUploadState.upload_id == ticket.upload_id)
            .values(lease_until=datetime(2000, 1, 1, tzinfo=UTC))
        )
    recovered = await bulk.service.recover_original(
        "issuer|editor", "north", batch.id, item.id, BulkAction(expected_revision=batch.revision), "recover"
    )
    assert recovered.status == "staging" and recovered.revision == batch.revision + 2
    replacement = await bulk.service.reserve_stream(
        "issuer|editor", "north", batch.id, item.id, "new-attempt"
    )
    assert replacement.write is True and replacement.upload_id != ticket.upload_id
    await bulk.service.abort_stream("north", replacement)
    assert not any(bulk.service.storage.configured().root.rglob("*.blob"))


async def test_list_checks_current_authority_after_last_awaited_item_counts(bulk):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    from koinon.catalog.errors import AccessDenied

    await bulk.service.create("issuer|editor", "north", request(bulk.target), "list-revocation")
    original = bulk.service.records.counts
    calls = 0

    async def revoke_after_last_counts(batch):
        nonlocal calls
        counts = await original(batch)
        calls += 1
        if calls == 2:
            async with bulk.context.get_bean(DataSourceRegistry).primary.engine.begin() as connection:
                await connection.execute(
                    update(Membership).where(Membership.id == "editor").values(active=False)
                )
        return counts

    bulk.service.records.counts = revoke_after_last_counts
    with pytest.raises(AccessDenied):
        await bulk.service.list("issuer|editor", "north")


async def test_dataset_admission_reserves_file_version_and_native_ids_before_any_processing(bulk):
    from uuid import UUID

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.knowledge.bulk.repositories import BulkRepository

    body = request(bulk.target, b"a,b\n1,2\n").model_dump(mode="json")
    body["items"][0]["mode"] = "dataset"
    manifest = FileBatchCreate.model_validate(body)
    batch = await bulk.service.create("issuer|editor", "north", manifest, "dataset-create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    assert item.file_version_id is not None
    version = await bulk.catalog.get("issuer|editor", "north", item.file_version_id)
    assert (
        version.kind == "index_version" and version.parent_id == item.asset_id and version.status == "pending"
    )
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).primary):
        row = await bulk.context.get_bean(BulkRepository).item(batch.id, item.id)
        reserved = dict(row.reservation_json)
        assert str(UUID(reserved["native_dataset_id"])) == reserved["native_dataset_id"]
        assert str(UUID(reserved["native_file_id"])) == reserved["native_file_id"]
        assert reserved["catalog_file_version_id"] == item.file_version_id
        assert row.native_workspace_id is None and row.winning_upload_id is None and row.job_id is None
    replay = await bulk.service.create("issuer|editor", "north", manifest, "dataset-create")
    assert replay.id == batch.id
    assert (await bulk.service.items("issuer|editor", "north", batch.id)).items[
        0
    ].file_version_id == item.file_version_id
    assert len(await bulk.catalog.list("issuer|editor", "north", kind="index_version")) == 1


async def test_archived_reserved_asset_during_upload_cannot_publish_original_winner(bulk):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.bulk.repositories import BulkRepository

    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "archive-during-upload")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    original = bulk.service.storage.put

    async def archive_after_write(*args):
        await original(*args)
        await bulk.catalog.update("issuer|editor", "north", item.asset_id, {"status": "archived"})

    bulk.service.storage.put = archive_after_write
    with pytest.raises(AccessDenied):
        await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).primary):
        stored = await bulk.context.get_bean(BulkRepository).item(batch.id, item.id)
        assert stored.winning_upload_id is None and stored.status == "awaiting_upload"


async def test_archived_dataset_file_version_cannot_admit_original_body(bulk):
    from koinon.catalog.errors import AccessDenied

    body = request(bulk.target).model_dump(mode="json")
    body["items"][0]["mode"] = "dataset"
    batch = await bulk.service.create(
        "issuer|editor", "north", FileBatchCreate.model_validate(body), "dataset-archive"
    )
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    await bulk.catalog.update("issuer|editor", "north", item.file_version_id, {"status": "archived"})
    with pytest.raises(AccessDenied):
        await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "never-read-body")
    assert not any(bulk.service.storage.configured().root.rglob("*.blob"))
