# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

import pytest
from test_connection_repository import stored as stored

from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject


@pytest.fixture
async def mappings(stored):
    from koinon.integrations.content_sources.mapping_repository import SourceMappingRepository

    _, session = stored
    mapping = SourceMapping(
        id="mapping",
        tenant_id="tenant",
        owner="issuer|alice",
        connection_id="connection",
        provider="google_drive",
        issuer="https://accounts.google.com",
        external_subject="provider-alice",
        drive_id="drive",
        root_id="root",
        workspace_id="workspace",
        project_id="project",
        parent_id="folder",
        request_json={"recursive": True, "removal_policy": "retire"},
        request_sha256="a" * 64,
        status="active",
        revision=1,
        reviewed_at=datetime.now(UTC),
    )
    origin = SourceObject(
        id="origin",
        tenant_id="tenant",
        mapping_id="mapping",
        item_id="remote-file",
        generation=1,
        mapping_revision=1,
        remote_version="v1",
        state="pending",
    )
    session.add_all([mapping, origin])
    await session.commit()
    return SourceMappingRepository(session=session), session, mapping, origin


async def test_mapping_lookup_is_owner_and_tenant_bound(mappings):
    repository, _, _, _ = mappings
    assert (await repository.owned("tenant", "issuer|alice", "mapping")).root_id == "root"
    assert await repository.owned("tenant", "issuer|bob", "mapping") is None
    assert await repository.owned("other", "issuer|alice", "mapping") is None


async def test_observation_generation_rejects_stale_remote_replacement(mappings):
    repository, session, _, origin = mappings
    assert await repository.observe(
        "tenant", "mapping", 1, "origin", 1, connection_revision=1, version="v2", state="pending"
    )
    await session.commit()
    assert not await repository.observe(
        "tenant", "mapping", 1, "origin", 1, connection_revision=1, version="old", state="pending"
    )
    await session.refresh(origin)
    assert origin.generation == 2 and origin.remote_version == "v2"


@pytest.mark.parametrize("change", ["mapping_revision", "paused", "disconnected", "other_tenant"])
async def test_new_observation_requires_current_active_mapping_and_import_connection(mappings, change):
    repository, session, mapping, origin = mappings
    if change == "mapping_revision":
        mapping.revision += 1
    elif change == "paused":
        mapping.status = "paused"
    elif change == "disconnected":
        from koinon.integrations.content_sources.entities import PersonalSourceConnection

        connection = await session.get(PersonalSourceConnection, "connection")
        connection.status = "disconnected"
    await session.commit()
    assert not await repository.observe(
        "other" if change == "other_tenant" else "tenant",
        "mapping",
        1,
        "origin",
        1,
        connection_revision=1,
        version="v2",
        state="pending",
    )
    await session.refresh(origin)
    assert origin.generation == 1


@pytest.mark.parametrize("state", ["deleted", "removed", "excluded"])
async def test_retirement_fences_old_generation_and_does_not_recreate_excluded_objects(mappings, state):
    repository, session, _, origin = mappings
    assert await repository.observe(
        "tenant", "mapping", 1, "origin", 1, connection_revision=1, version=None, state=state
    )
    await session.commit()
    assert not await repository.observe(
        "tenant", "mapping", 1, "origin", 1, connection_revision=1, version="v1", state="pending"
    )
    if state == "excluded":
        assert not await repository.observe(
            "tenant", "mapping", 1, "origin", 2, connection_revision=1, version="v3", state="pending"
        )
    await session.refresh(origin)
    assert origin.generation == 2 and origin.state == state


@pytest.mark.parametrize("change", ["owner", "provider", "account", "issuer", "config", "refresh"])
async def test_observation_rejects_changed_import_authority(mappings, change):
    from koinon.integrations.content_sources.entities import PersonalSourceConnection

    repository, session, _, origin = mappings
    connection = await session.get(PersonalSourceConnection, "connection")
    if change == "owner":
        connection.owner = "issuer|bob"
    elif change == "provider":
        connection.provider = "onedrive"
    elif change == "account":
        connection.external_subject = "another-account"
    elif change == "issuer":
        connection.issuer = "https://other.example"
    elif change == "config":
        connection.config_fingerprint = "changed"
    else:
        connection.refresh_operation = "in-flight-rotation"
    await session.commit()
    assert not await repository.observe(
        "tenant", "mapping", 1, "origin", 1, connection_revision=1, version="v2", state="pending"
    )
    await session.refresh(origin)
    assert origin.generation == 1


async def test_identical_observation_does_not_advance_generation(mappings):
    repository, session, _, origin = mappings
    assert await repository.observe(
        "tenant", "mapping", 1, "origin", 1, connection_revision=1, version="v1", state="pending"
    )
    await session.commit()
    await session.refresh(origin)
    assert origin.generation == 1


async def test_object_from_another_mapping_is_not_modified(mappings):
    repository, session, _, origin = mappings
    origin.mapping_id = "another-mapping"
    await session.commit()
    assert not await repository.observe(
        "tenant", "mapping", 1, "origin", 1, connection_revision=1, version="v2", state="pending"
    )
    await session.refresh(origin)
    assert origin.generation == 1


async def test_observation_captured_before_credential_rotation_is_rejected(mappings):
    from koinon.integrations.content_sources.entities import PersonalSourceConnection

    repository, session, _, origin = mappings
    connection = await session.get(PersonalSourceConnection, "connection")
    connection.revision += 1
    await session.commit()
    assert not await repository.observe(
        "tenant", "mapping", 1, "origin", 1, connection_revision=1, version="v2", state="pending"
    )
    await session.refresh(origin)
    assert origin.generation == 1


@pytest.mark.parametrize("current", ["imported", "failed"])
async def test_repeated_source_version_does_not_restart_completed_or_failed_ingestion(mappings, current):
    repository, session, _, origin = mappings
    origin.state = current
    await session.commit()
    assert await repository.observe(
        "tenant", "mapping", 1, "origin", 1, connection_revision=1, version="v1", state="pending"
    )
    await session.commit()
    await session.refresh(origin)
    assert origin.generation == 1 and origin.state == current
