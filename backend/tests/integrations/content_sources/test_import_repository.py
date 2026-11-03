# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Controlled primary receipts; these tests do not qualify a live provider or native publication hook."""

from datetime import UTC, datetime, timedelta

import pytest
from test_connection_repository import stored as stored
from test_mapping_repository import mappings as mappings

from koinon.integrations.content_sources.import_entities import SourceImportAttempt as SourceImportAttempt
from koinon.jobs.entities import Job as Job
from koinon.knowledge.bulk.entities import BulkBatch, BulkItem


@pytest.fixture
async def imports(mappings):
    from koinon.integrations.content_sources.import_repository import SourceImportRepository

    _, session, mapping, origin = mappings
    batch = BulkBatch(
        id="batch",
        tenant_id="tenant",
        subject="issuer|alice",
        workspace_id="workspace",
        project_id="project",
        parent_id="folder",
        key_hash="b" * 64,
        request_hash="c" * 64,
        request_json={},
        total_bytes=7,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    item = BulkItem(
        id="item",
        batch_id="batch",
        ordinal=0,
        client_item_id="remote-file",
        filename="report.docx",
        mode="document",
        size_bytes=7,
        sha256="d" * 64,
        source_id="source",
        asset_id="asset",
        status="awaiting_upload",
        native_workspace_id="native-space",
    )
    session.add_all([batch, item])
    await session.commit()
    return SourceImportRepository(session=session), session, mapping, origin, batch, item


async def reserve(repository):
    return await repository.reserve(
        "tenant",
        "mapping",
        1,
        "origin",
        1,
        "item",
        connection_revision=1,
    )


def committed(item):
    item.status = "succeeded"
    item.native_id = "native-document"
    item.receipt_json = {
        "domain": "canon",
        "native_workspace_id": "native-space",
        "native_source_id": "native-source",
        "native_asset_id": "native-document",
        "sha256": "d" * 64,
        "size_bytes": 7,
        "source_version_id": "native-version",
        "extraction_id": "extraction",
        "n_chunks": 1,
        "object_key": "private-original",
        "file_version_id": None,
        "native_file_id": None,
        "tables": [],
    }


async def test_reservation_is_stable_before_enqueue_and_not_a_commit(imports):
    repository, session, _, _, _, item = imports
    first = await reserve(repository)
    await session.commit()
    second = await reserve(repository)
    assert first.id == second.id and first.intake_item_id == "item"
    assert item.status == "awaiting_upload" and first.receipt_json is None
    assert not await repository.record_commit("tenant", first.id, connection_revision=1)


@pytest.mark.parametrize("change", ["tenant", "owner", "destination", "cancelled", "already_started"])
async def test_reservation_rejects_other_scope_and_already_admitted_intake(imports, change):
    repository, session, _, _, batch, item = imports
    if change == "tenant":
        batch.tenant_id = "other"
    elif change == "owner":
        batch.subject = "issuer|bob"
    elif change == "destination":
        batch.parent_id = "another-folder"
    elif change == "cancelled":
        batch.cancelled = True
    else:
        item.status = "running"
    await session.commit()
    assert await reserve(repository) is None


async def test_exact_native_receipt_is_bound_once_and_replay_cannot_change_it(imports):
    repository, session, _, origin, _, item = imports
    attempt = await reserve(repository)
    committed(item)
    await session.commit()
    assert await repository.record_commit("tenant", attempt.id, connection_revision=1)
    await session.commit()
    assert await repository.record_commit("tenant", attempt.id, connection_revision=1)
    await session.refresh(attempt)
    assert attempt.receipt_json["source_version_id"] == "native-version"
    assert origin.state == "imported"
    item.receipt_json = {**item.receipt_json, "source_version_id": "another-version"}
    await session.commit()
    assert not await repository.record_commit("tenant", attempt.id, connection_revision=1)
    await session.refresh(attempt)
    assert attempt.receipt_json["source_version_id"] == "native-version"


@pytest.mark.parametrize("change", ["newer", "excluded", "mapping", "hash", "native_scope", "account"])
async def test_late_commit_is_fenced_without_erasing_native_effects(imports, change):
    from koinon.integrations.content_sources.entities import PersonalSourceConnection

    repository, session, mapping, origin, _, item = imports
    attempt = await reserve(repository)
    committed(item)
    if change == "newer":
        origin.generation += 1
        origin.remote_version = "v2"
    elif change == "excluded":
        origin.generation += 1
        origin.state = "excluded"
    elif change == "mapping":
        mapping.revision += 1
    elif change == "hash":
        item.receipt_json = {**item.receipt_json, "sha256": "e" * 64}
    elif change == "native_scope":
        item.receipt_json = {**item.receipt_json, "native_workspace_id": "other"}
    else:
        connection = await session.get(PersonalSourceConnection, "connection")
        connection.revision += 1
    await session.commit()
    assert not await repository.record_commit("tenant", attempt.id, connection_revision=1)
    await session.refresh(attempt)
    assert attempt.receipt_json is None
    assert item.status == "succeeded" and item.native_id == "native-document"


async def test_existing_reservation_still_checks_current_intake_owner(imports):
    repository, session, _, _, batch, _ = imports
    assert await reserve(repository)
    batch.subject = "issuer|bob"
    await session.commit()
    assert await reserve(repository) is None


async def test_one_intake_item_cannot_be_reserved_for_two_origins(imports):
    from koinon.integrations.content_sources.mapping_entities import SourceObject

    repository, session, _, _, _, _ = imports
    assert await reserve(repository)
    session.add(
        SourceObject(
            id="second",
            tenant_id="tenant",
            mapping_id="mapping",
            item_id="another-file",
            generation=1,
            mapping_revision=1,
            remote_version="v1",
            state="pending",
        )
    )
    await session.commit()
    assert (
        await repository.reserve(
            "tenant",
            "mapping",
            1,
            "second",
            1,
            "item",
            connection_revision=1,
        )
        is None
    )


async def test_acknowledgment_rereads_a_commit_that_finished_before_its_fence(imports, monkeypatch):
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker

    repository, session, _, _, _, item = imports
    attempt = await reserve(repository)
    committed(item)
    await session.commit()
    recorded_at = datetime(2026, 11, 1, tzinfo=UTC)
    original_fence = repository._fence

    async def concurrent_commit(*args):
        async with async_sessionmaker(session.bind, expire_on_commit=False)() as other:
            await other.execute(
                update(SourceImportAttempt)
                .where(SourceImportAttempt.id == attempt.id)
                .values(
                    receipt_json=item.receipt_json,
                    committed_at=recorded_at,
                )
            )
            await other.commit()
        return await original_fence(*args)

    monkeypatch.setattr(repository, "_fence", concurrent_commit)
    assert await repository.record_commit("tenant", attempt.id, connection_revision=1)
    await session.commit()
    await session.refresh(attempt)
    assert attempt.committed_at == recorded_at
