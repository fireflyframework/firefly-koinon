# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persisted reader choices use native units and real PostgreSQL snapshot guards."""

from uuid import uuid4

import pytest
from test_connection_lifecycle import begin, complete
from test_connection_lifecycle import lifecycle as lifecycle
from test_source_migration_postgres import source_database as source_database

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput, ReaderSourceSelection
from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections

pytestmark = [pytest.mark.integration, pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)]


async def setup(lifecycle):
    connections, _, _, context = lifecycle
    start, state = await begin(connections)
    await complete(connections, start, state)
    choices = context.get_bean(SourceReaderSelections)
    selected = ReaderSourceSelection(provider="google_drive", connection_id=start.connection_id)
    return choices, selected


async def test_reader_choice_is_private_cas_and_idempotent(lifecycle):
    choices, selected = await setup(lifecycle)
    request = ReaderSelectionInput(expected_revision=0, operation_id=uuid4(), connections=[selected])
    result = await choices.replace("issuer|alice", "tenant", request)
    assert result.revision == 1 and result.connections == (selected,)
    assert await choices.replace("issuer|alice", "tenant", request) == result
    assert (await choices.get("issuer|bob", "tenant")).connections == ()
    with pytest.raises(SourceError, match="authority_changed"):
        await choices.replace("issuer|alice", "tenant", request.model_copy(update={"connections": []}))
    with pytest.raises(SourceError, match="authority_changed"):
        await choices.replace("issuer|alice", "tenant", request.model_copy(update={"operation_id": uuid4()}))
    assert await choices.get("issuer|alice", "tenant") == result


async def test_reader_cannot_select_another_persons_connection(lifecycle):
    choices, selected = await setup(lifecycle)
    request = ReaderSelectionInput(expected_revision=0, operation_id=uuid4(), connections=[selected])
    with pytest.raises(SourceError, match="access_denied"):
        await choices.replace("issuer|bob", "tenant", request)
    assert (await choices.get("issuer|bob", "tenant")).revision == 0
    with pytest.raises(SourceError, match="access_denied"):
        await choices.resolve("issuer|bob", "tenant", (selected,))


async def test_empty_override_and_changed_default_have_distinct_semantics(lifecycle):
    choices, selected = await setup(lifecycle)
    await choices.replace(
        "issuer|alice",
        "tenant",
        ReaderSelectionInput(expected_revision=0, operation_id=uuid4(), connections=[selected]),
    )
    saved = await choices.resolve("issuer|alice", "tenant")
    explicit_empty = await choices.resolve("issuer|alice", "tenant", ())
    assert saved.connections == (selected,) and explicit_empty.connections == ()
    await choices.replace(
        "issuer|alice",
        "tenant",
        ReaderSelectionInput(expected_revision=1, operation_id=uuid4(), connections=[]),
    )
    with pytest.raises(SourceError, match="authority_changed"):
        await choices.confirm("issuer|alice", "tenant", saved)
    await choices.confirm("issuer|alice", "tenant", explicit_empty)
    assert (await choices.get("issuer|alice", "tenant")).revision == 2


async def test_workspace_only_reader_can_choose_own_source_connection(lifecycle):
    from koinon.catalog.entities import CatalogEntry
    from koinon.catalog.repositories import CatalogRepository, MembershipRepository
    from koinon.security.authority import primary_authority

    choices, selected = await setup(lifecycle)
    context = lifecycle[3]
    async with primary_authority(read_only=False):
        await context.get_bean(CatalogRepository).save(
            CatalogEntry(
                id="private-space",
                tenant_id="tenant",
                kind="workspace",
                name="Private space",
                workspace_id="private-space",
                created_by="issuer|alice",
            )
        )
        repository = context.get_bean(MembershipRepository)
        member = await repository.find_by_id("issuer|alice")
        member.workspace_id = "private-space"
        await repository.save(member)
    result = await choices.replace(
        "issuer|alice",
        "tenant",
        ReaderSelectionInput(expected_revision=0, operation_id=uuid4(), connections=[selected]),
    )
    assert result.connections == (selected,)
