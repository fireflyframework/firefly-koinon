# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Upload receipt replay cannot take ownership of another request's write."""

from datetime import UTC, datetime
from hashlib import sha256

import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException
from test_bulk_native import bulk as bulk
from test_bulk_native import request

from koinon.knowledge.bulk.dtos import BulkAction
from koinon.knowledge.bulk.repositories import BulkRepository


async def expire_writer(bulk, upload_id):
    from sqlalchemy import update

    from koinon.knowledge.bulk.entities import BulkUploadState

    registry = bulk.context.get_bean(DataSourceRegistry)
    async with registry.get("primary").engine.begin() as connection:
        await connection.execute(
            update(BulkUploadState)
            .where(BulkUploadState.upload_id == upload_id)
            .values(lease_until=datetime(2000, 1, 1, tzinfo=UTC))
        )


async def test_persisted_unacknowledged_replay_cannot_publish_or_release_original_writer(bulk):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    await bulk.service.storage.put(writer.object_key, b"original", writer.sha256)
    replay = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    with pytest.raises(ConflictException) as pending:
        await bulk.service.finish_stream(
            "issuer|editor", "north", batch.id, item.id, replay, None, 8, sha256(b"original").hexdigest()
        )
    assert pending.value.code == "BULK_UPLOAD_PENDING"
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert (await records.quota("global:uploads")).active_uploads == 1
        assert (await records.item(batch.id, item.id)).winning_upload_id is None
    receipt = await bulk.service.finish_stream(
        "issuer|editor", "north", batch.id, item.id, writer, b"original", 8, writer.sha256
    )
    assert receipt.receipt_id == writer.upload_id


async def test_expired_writer_cannot_publish_after_recovery_and_late_bytes_remain_recoverable(bulk):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    await expire_writer(bulk, writer.upload_id)
    recovered = await bulk.service.recover_original(
        "issuer|editor",
        "north",
        batch.id,
        item.id,
        BulkAction(expected_revision=batch.revision),
        "recover-missing",
    )
    await bulk.service.storage.put(writer.object_key, b"original", writer.sha256)
    with pytest.raises(ConflictException) as lost:
        await bulk.service._finish_upload("issuer|editor", "north", batch.id, item.id, writer)
    assert lost.value.code == "BULK_UPLOAD_LEASE_LOST"
    await bulk.service.abort_stream("north", writer)
    current = await bulk.service.recover_original(
        "issuer|editor",
        "north",
        batch.id,
        item.id,
        BulkAction(expected_revision=recovered.revision),
        "recover-late",
    )
    assert current.counts == {"staged": 1}
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert (await records.quota("global:uploads")).active_uploads == 0
        assert (await records.quota("global:recoveries")).active_uploads == 0
        assert (await records.quota("tenant:north")).reserved_bytes == 8


async def test_live_writer_recovery_requires_expiry_even_after_original_is_persisted(bulk):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    await bulk.service.storage.put(writer.object_key, b"original", writer.sha256)
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
    await bulk.service.abort_stream("north", writer)


async def test_recovery_crash_after_committed_fence_resumes_read_only_without_new_upload(bulk):
    from sqlalchemy import update

    from koinon.knowledge.bulk.entities import BulkRecovery, BulkUploadState

    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    await bulk.service.storage.put(writer.object_key, b"original", writer.sha256)
    await expire_writer(bulk, writer.upload_id)
    body = BulkAction(expected_revision=batch.revision)
    crashed = await bulk.service._recovery_ticket(
        "issuer|editor", "north", batch.id, item.id, body, "recover"
    )
    assert crashed is not None
    registry = bulk.context.get_bean(DataSourceRegistry)
    async with registry.get("primary").engine.begin() as connection:
        for entity in (BulkRecovery, BulkUploadState):
            await connection.execute(update(entity).values(lease_until=datetime(2000, 1, 1, tzinfo=UTC)))
    resumed = await bulk.service.recover_original(
        "issuer|editor", "north", batch.id, item.id, body, "recover"
    )
    assert resumed.counts == {"staged": 1}
    async with infrastructure_unit(registry.get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert await records.upload_count(item.id) == 1
        assert (await records.quota("tenant:north")).reserved_bytes == 8
        assert (await records.quota("global:recoveries")).active_uploads == 0
        generation = (await records.upload_state(writer.upload_id)).generation
    replay = await bulk.service.recover_original("issuer|editor", "north", batch.id, item.id, body, "recover")
    assert replay.revision == resumed.revision
    async with infrastructure_unit(registry.get("primary")):
        assert (await records.upload_state(writer.upload_id)).generation == generation


async def test_recovery_cannot_publish_after_authority_revocation_during_verification(bulk):
    from koinon.catalog.errors import AccessDenied

    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    await bulk.service.storage.put(writer.object_key, b"original", writer.sha256)
    await expire_writer(bulk, writer.upload_id)
    read = bulk.service.storage.read

    async def read_then_revoke(*args, **kwargs):
        result = await read(*args, **kwargs)
        member = await bulk.members.find_by_id("editor")
        member.active = False
        await bulk.members.save(member)
        return result

    bulk.service.storage.read = read_then_revoke
    with pytest.raises(AccessDenied):
        await bulk.service.recover_original(
            "issuer|editor",
            "north",
            batch.id,
            item.id,
            BulkAction(expected_revision=batch.revision),
            "recover",
        )
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert (await records.item(batch.id, item.id)).winning_upload_id is None
        assert (await records.quota("global:recoveries")).active_uploads == 0


async def test_late_physical_write_after_missing_recovery_never_regains_publication(bulk, monkeypatch):
    import asyncio
    import threading

    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    store = bulk.service.storage.configured()
    original_write = store._write
    started, release = threading.Event(), threading.Event()

    def delayed(*args, **kwargs):
        started.set()
        if not release.wait(10):
            raise OSError("Owned test write was not released")
        return original_write(*args, **kwargs)

    monkeypatch.setattr(store, "_write", delayed)
    writer = asyncio.create_task(
        bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    )
    try:
        assert await asyncio.to_thread(started.wait, 5)
        async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
            records = bulk.context.get_bean(BulkRepository)
            upload = await records.latest_upload(item.id)
        await expire_writer(bulk, upload.id)
        recovered = await bulk.service.recover_original(
            "issuer|editor",
            "north",
            batch.id,
            item.id,
            BulkAction(expected_revision=batch.revision),
            "recover-missing",
        )
        assert recovered.counts == {"awaiting_upload": 1}
    finally:
        release.set()
    with pytest.raises(ConflictException) as lost:
        await writer
    assert lost.value.code == "BULK_UPLOAD_LEASE_LOST"
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        assert (await records.item(batch.id, item.id)).winning_upload_id is None
        assert (await records.quota("tenant:north")).reserved_bytes == 8
        assert (await records.quota("global:uploads")).active_uploads == 0
    assert (
        await bulk.service.storage.read(upload.object_key, 8, sha256(b"original").hexdigest()) == b"original"
    )


async def test_recovery_result_cannot_publish_across_an_intervening_batch_revision(bulk):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    await bulk.service.storage.put(writer.object_key, b"original", writer.sha256)
    await expire_writer(bulk, writer.upload_id)
    body = BulkAction(expected_revision=batch.revision)
    ticket = await bulk.service._recovery_ticket("issuer|editor", "north", batch.id, item.id, body, "recover")
    current = await bulk.service.get("issuer|editor", "north", batch.id)
    await bulk.service.cancel(
        "issuer|editor", "north", batch.id, BulkAction(expected_revision=current.revision), "cancel"
    )
    with pytest.raises(ConflictException) as changed:
        await bulk.service._recover_original(
            "issuer|editor", "north", batch.id, item.id, body, "recover", ticket, True
        )
    assert changed.value.code == "BULK_REVISION_CONFLICT"
    await bulk.service._abort_recovery("north", ticket)
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert (await records.item(batch.id, item.id)).winning_upload_id is None
        assert (await records.quota("global:recoveries")).active_uploads == 0


async def test_owner_token_does_not_authorize_a_substituted_object_locator(bulk):
    from dataclasses import replace

    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    forged = replace(writer, object_key="bulk/foreign.blob")
    with pytest.raises(ConflictException) as identity:
        await bulk.service.finish_stream(
            "issuer|editor", "north", batch.id, item.id, forged, b"original", 8, forged.sha256
        )
    assert identity.value.code == "BULK_UPLOAD_CONFLICT"
    assert not any(bulk.service.storage.configured().root.rglob("*.blob"))


async def test_cloud_capabilities_report_object_storage_and_database_fence_without_posix_claim(bulk):
    settings = bulk.service.settings
    settings.storage_root = None
    settings.storage_backend = "azure"
    settings.azure_account_url = "https://owned.blob.core.windows.net"
    settings.azure_container = "owned-private"
    capabilities = await bulk.service.capabilities("issuer|editor", "north", bulk.target["workspace_id"])
    assert capabilities.configured is True
    assert capabilities.staging_backend == "private_azure_blob"
    assert capabilities.staging_topology == "shared_private_object_store"
    assert capabilities.writer_fence == "primary_database_generation_lease"


async def test_file_policy_output_keeps_fresh_authority_participant_in_its_fixed_primary_snapshot(bulk):
    from pyfly.data.transaction import current_unit_of_work

    from koinon.security.authority import primary_authority

    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    original = bulk.service.authority.destination

    async def observe(*args, **kwargs):
        outer = current_unit_of_work("primary")
        async with primary_authority(fresh=True) as authority:
            assert authority is outer
        return await original(*args, **kwargs)

    bulk.service.authority.destination = observe
    assert (await bulk.service.get("issuer|editor", "north", batch.id)).id == batch.id


async def test_expired_logical_writer_does_not_free_a_live_process_body_or_sdk_slot(bulk):
    from pyfly.kernel import RateLimitException

    bulk.service.settings.max_local_storage_operations = 1
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    await expire_writer(bulk, writer.upload_id)
    await bulk.service.recover_original(
        "issuer|editor", "north", batch.id, item.id, BulkAction(expected_revision=batch.revision), "recover"
    )
    with pytest.raises(RateLimitException) as physical:
        await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "replacement")
    assert physical.value.code == "BULK_STORAGE_IO_LIMIT"
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert await records.upload_count(item.id) == 1
    await bulk.service.abort_stream("north", writer)
    replacement = await bulk.service.reserve_stream(
        "issuer|editor", "north", batch.id, item.id, "replacement"
    )
    assert replacement.write and replacement.upload_id != writer.upload_id
    await bulk.service.abort_stream("north", replacement)


async def test_ambiguous_persisted_write_is_only_reconciled_by_reading_original_bytes(bulk):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    original = bulk.service.storage.put
    calls = 0

    async def persist_then_disconnect(*args):
        nonlocal calls
        calls += 1
        await original(*args)
        raise OSError("Owned ambiguous acknowledgment")

    bulk.service.storage.put = persist_then_disconnect
    with pytest.raises(OSError):
        await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    with pytest.raises(ConflictException) as pending:
        await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    assert pending.value.code == "BULK_UPLOAD_PENDING"
    recovered = await bulk.service.recover_original(
        "issuer|editor", "north", batch.id, item.id, BulkAction(expected_revision=batch.revision), "recover"
    )
    assert recovered.counts == {"staged": 1} and calls == 1


async def test_new_admission_fences_expired_logical_permit_without_replaying_original(bulk):
    bulk.service.settings.max_uploads_per_tenant = 1
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    old = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "old")
    await expire_writer(bulk, old.upload_id)
    new = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "new")
    assert new.write and new.upload_id != old.upload_id
    with pytest.raises(ConflictException) as lost:
        await bulk.service._finish_upload("issuer|editor", "north", batch.id, item.id, old)
    assert lost.value.code == "BULK_UPLOAD_LEASE_LOST"
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert (await records.quota("tenant:north")).reserved_bytes == 16
        assert (await records.quota("global:uploads")).active_uploads == 1
        assert (await records.item(batch.id, item.id)).winning_upload_id is None
    assert not any(bulk.service.storage.configured().root.rglob("*.blob"))
    await bulk.service.abort_stream("north", old)
    await bulk.service.abort_stream("north", new)


@pytest.mark.parametrize("operation", ["finish", "recover"])
async def test_external_staging_io_rejects_an_ambient_primary_unit(bulk, operation):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    if operation == "recover":
        await bulk.service.abort_stream("north", writer)
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        with pytest.raises(ConflictException) as ambient:
            if operation == "finish":
                await bulk.service.finish_stream(
                    "issuer|editor", "north", batch.id, item.id, writer, b"original", 8, writer.sha256
                )
            else:
                await bulk.service.recover_original(
                    "issuer|editor",
                    "north",
                    batch.id,
                    item.id,
                    BulkAction(expected_revision=batch.revision),
                    "recover",
                )
        assert ambient.value.code == "BULK_AMBIENT_TRANSACTION"
    await bulk.service.abort_stream("north", writer)


async def test_recovery_budget_namespace_cannot_collide_with_an_opaque_foreign_tenant_id(bulk):
    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import TenantRepository

    foreign = "recoveries:north"
    await bulk.context.get_bean(TenantRepository).save(Tenant(id=foreign, name="Synthetic foreign tenant"))
    await bulk.members.save(
        Membership(id="foreign-member", subject="issuer|editor", tenant_id=foreign, role="editor")
    )
    workspace = await bulk.catalog.create("issuer|editor", foreign, kind="workspace", name="Foreign")
    project = await bulk.catalog.create(
        "issuer|editor", foreign, kind="project", name="Project", parent_id=workspace.id
    )
    parent = await bulk.catalog.create(
        "issuer|editor", foreign, kind="collection", name="Collection", parent_id=project.id
    )
    foreign_batch = await bulk.service.create(
        "issuer|editor",
        foreign,
        request(
            {
                "workspace_id": workspace.id,
                "project_id": project.id,
                "parent_id": parent.id,
            }
        ),
        "foreign-batch",
    )
    foreign_item = (await bulk.service.items("issuer|editor", foreign, foreign_batch.id)).items[0]
    foreign_writer = await bulk.service.reserve_stream(
        "issuer|editor", foreign, foreign_batch.id, foreign_item.id, "foreign-upload"
    )
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "north-batch")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "north-upload")
    await bulk.service.storage.put(writer.object_key, b"original", writer.sha256)
    await bulk.service.abort_stream("north", writer)
    bulk.service.settings.max_recoveries_per_tenant = 1
    result = await bulk.service.recover_original(
        "issuer|editor", "north", batch.id, item.id, BulkAction(expected_revision=batch.revision), "recover"
    )
    assert result.counts == {"staged": 1}
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert (await records.quota("tenant:" + foreign)).active_uploads == 1
        assert (await records.quota("global:uploads")).active_uploads == 1
    await bulk.service.abort_stream(foreign, foreign_writer)


async def test_pending_recovery_owns_its_action_key_before_any_external_read(bulk):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    staged = await bulk.service.get("issuer|editor", "north", batch.id)
    recovery = await bulk.service._recovery_ticket(
        "issuer|editor",
        "north",
        batch.id,
        item.id,
        BulkAction(expected_revision=staged.revision),
        "shared-action-key",
    )
    current = await bulk.service.get("issuer|editor", "north", batch.id)
    with pytest.raises(ConflictException) as reserved:
        await bulk.service.submit(
            "issuer|editor",
            "north",
            batch.id,
            BulkAction(expected_revision=current.revision),
            "shared-action-key",
        )
    assert reserved.value.code == "IDEMPOTENCY_CONFLICT"
    await bulk.service._abort_recovery("north", recovery)


async def test_recovery_cleanup_cannot_release_a_different_action_with_the_same_generation(bulk):
    from dataclasses import replace

    recoveries = []
    for index in range(2):
        batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), f"batch-{index}")
        item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
        await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", f"upload-{index}")
        current = await bulk.service.get("issuer|editor", "north", batch.id)
        recoveries.append(
            await bulk.service._recovery_ticket(
                "issuer|editor",
                "north",
                batch.id,
                item.id,
                BulkAction(expected_revision=current.revision),
                f"recover-{index}",
            )
        )
    await bulk.service._abort_recovery("north", replace(recoveries[0], action_id=recoveries[1].action_id))
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert (await records.quota("global:recoveries")).active_uploads == 2
        assert (await records.recovery_by_id(recoveries[0].action_id)).permit_held is True
        assert (await records.recovery_by_id(recoveries[1].action_id)).permit_held is True
    for recovery in recoveries:
        await bulk.service._abort_recovery("north", recovery)
