# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual destination authority around metadata I/O and a short persistence fence."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pyfly.data.transaction import current_unit_of_work
from sqlalchemy import select, update
from test_connection_lifecycle import begin, complete
from test_connection_lifecycle import lifecycle as lifecycle

from koinon.catalog.entities import CatalogEntry, Membership
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.integrations.content_sources.browse import PersonalSourceBrowser
from koinon.integrations.content_sources.dtos import RemoteItem
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceMapping
from koinon.integrations.content_sources.mapping_repository import SourceMappingRepository
from koinon.integrations.content_sources.mapping_review import SourceMappingReviews
from koinon.security.authority import primary_authority


@pytest.fixture
async def review(lifecycle, monkeypatch):
    connections, _, _, context = lifecycle
    start, state = await begin(connections)
    connection = await complete(connections, start, state)
    records = context.get_bean(SourceMappingRepository)
    async with primary_authority(read_only=False):
        await records._require_session().execute(
            update(Membership).where(Membership.id == "issuer|alice").values(role="editor")
        )
    catalog = context.get_bean(CatalogService)
    workspace = await catalog.create("issuer|alice", "tenant", kind="workspace", name="Own workspace")
    project = await catalog.create(
        "issuer|alice", "tenant", kind="project", name="Own project", parent_id=workspace.id
    )
    folder = await catalog.create(
        "issuer|alice", "tenant", kind="collection", name="Own folder", parent_id=project.id
    )
    request = MappingReviewInput(
        connection_id=connection.id,
        drive_id="drive",
        root_id="selected",
        recursive=True,
        removal_policy="retire",
        destination={"workspace_id": workspace.id, "project_id": project.id, "parent_id": folder.id},
    )
    state = SimpleNamespace(
        parents={"selected": ("root",), "other": ("root",), "root": ()}, calls=[], during=None
    )

    @asynccontextmanager
    async def source(scope, tokens):
        class Source:
            async def root(self):
                return await self.get_item("root")

            async def get_item(self, identifier):
                for name in ("primary", "canon", "structured"):
                    unit = current_unit_of_work(name)
                    assert unit is None or unit.completed
                await tokens.access_token(scope.account)
                state.calls.append(identifier)
                if state.during:
                    await state.during(identifier)
                return RemoteItem(
                    scope,
                    identifier,
                    "secret remote title",
                    "folder",
                    "v1",
                    None,
                    "",
                    parents=state.parents[identifier],
                )

        yield Source()

    monkeypatch.setattr(context.get_bean(PersonalSourceBrowser), "_source", source)
    yield SimpleNamespace(
        service=context.get_bean(SourceMappingReviews),
        records=records,
        request=request,
        state=state,
        connection=connection,
        context=context,
    )


async def rows(review):
    async with primary_authority():
        return list((await review.records._require_session().scalars(select(SourceMapping))).all())


async def test_review_is_inactive_minimal_and_expiring(review):
    result = await review.service.review("issuer|alice", "tenant", review.request)
    assert result.status == "reviewed" and result.expires_at > datetime.now(UTC)
    stored = (await rows(review))[0]
    assert stored.status == "reviewed" and stored.parent_id == review.request.destination.parent_id
    assert stored.reviewed_expires_at == result.expires_at
    assert "secret remote title" not in repr(stored.request_json)
    assert "access-one" not in repr(stored.request_json)
    assert review.state.calls == ["root", "selected", "root", "selected"]


@pytest.mark.parametrize("actor,tenant", [("issuer|bob", "tenant"), ("issuer|alice", "other")])
async def test_destination_or_owner_denial_happens_before_remote_io(review, actor, tenant):
    with pytest.raises((AccessDenied, SourceError)):
        await review.service.review(actor, tenant, review.request)
    assert review.state.calls == [] and await rows(review) == []


async def test_destination_editor_cannot_review_another_owners_connection(review):
    async with primary_authority(read_only=False):
        await review.records._require_session().execute(
            update(Membership).where(Membership.id == "issuer|bob").values(role="editor")
        )
    with pytest.raises(SourceError, match="access_denied"):
        await review.service.review("issuer|bob", "tenant", review.request)
    assert review.state.calls == []


async def test_nested_library_folder_is_rejected_without_flattening_or_remote_reads(review):
    nested = await review.context.get_bean(CatalogService).create(
        "issuer|alice",
        "tenant",
        kind="collection",
        name="Nested destination",
        parent_id=review.request.destination.parent_id,
    )
    target = review.request.destination.model_copy(update={"parent_id": nested.id})
    with pytest.raises(AccessDenied, match="ancestry differs"):
        await review.service.review(
            "issuer|alice", "tenant", review.request.model_copy(update={"destination": target})
        )
    assert review.state.calls == [] and await rows(review) == []


@pytest.mark.parametrize("change", ["membership", "destination", "grant", "scopes", "configuration"])
async def test_late_local_authority_change_rejects_persistence(review, change):
    async def alter(identifier):
        if len(review.state.calls) != 4:
            return
        async with primary_authority(read_only=False):
            session = review.records._require_session()
            if change == "membership":
                await session.execute(
                    update(Membership).where(Membership.id == "issuer|alice").values(role="viewer")
                )
            elif change == "destination":
                await session.execute(
                    update(CatalogEntry)
                    .where(CatalogEntry.id == review.request.destination.parent_id)
                    .values(parent_id=review.request.destination.workspace_id)
                )
            elif change == "grant":
                await session.execute(
                    update(PersonalSourceConnection)
                    .where(PersonalSourceConnection.id == review.connection.id)
                    .values(revision=PersonalSourceConnection.revision + 1)
                )
            elif change == "scopes":
                await session.execute(
                    update(PersonalSourceConnection)
                    .where(PersonalSourceConnection.id == review.connection.id)
                    .values(scopes=[])
                )
            else:
                review.service.connections.registrations.settings.providers["google_drive"]["client_id"] = (
                    "changed"
                )

    review.state.during = alter
    with pytest.raises((AccessDenied, SourceError)):
        await review.service.review("issuer|alice", "tenant", review.request)
    assert await rows(review) == []


async def test_ancestry_changed_between_observations_rejects_review(review):
    async def alter(identifier):
        if len(review.state.calls) == 3:
            review.state.parents["selected"] = ("other",)

    review.state.during = alter
    with pytest.raises(SourceError, match="version_changed"):
        await review.service.review("issuer|alice", "tenant", review.request)
    assert await rows(review) == []


async def test_second_review_rejects_overlap_without_exposing_existing_destination(review):
    first = await review.service.review("issuer|alice", "tenant", review.request)
    with pytest.raises(SourceError, match="scope_mismatch") as error:
        await review.service.review("issuer|alice", "tenant", review.request)
    assert first.id not in str(error.value)
    assert len(await rows(review)) == 1


async def test_cross_owner_overlap_returns_generic_error_and_no_local_details(review):
    first = await review.service.review("issuer|alice", "tenant", review.request)
    async with primary_authority(read_only=False):
        await review.records._require_session().execute(
            update(SourceMapping)
            .where(SourceMapping.id == first.id)
            .values(owner="issuer|bob", parent_id="private-folder")
        )
    with pytest.raises(SourceError) as error:
        await review.service.review("issuer|alice", "tenant", review.request)
    assert str(error.value) == "scope_mismatch"


@pytest.mark.parametrize("change", ["expired", "retired", "account", "drive"])
async def test_unrelated_or_expired_mapping_does_not_block_selected_root(review, change):
    first = await review.service.review("issuer|alice", "tenant", review.request)
    values = {
        "expired": {"reviewed_expires_at": datetime.now(UTC) - timedelta(seconds=1)},
        "retired": {"status": "retired"},
        "account": {"external_subject": "another-account"},
        "drive": {"drive_id": "another-drive"},
    }[change]
    async with primary_authority(read_only=False):
        await review.records._require_session().execute(
            update(SourceMapping).where(SourceMapping.id == first.id).values(**values)
        )
    result = await review.service.review("issuer|alice", "tenant", review.request)
    assert result.status == "reviewed" and len(await rows(review)) == 2


async def test_candidate_mapping_change_during_remote_io_rejects_review(review):
    first = await review.service.review(
        "issuer|alice", "tenant", review.request.model_copy(update={"root_id": "other"})
    )
    review.state.calls.clear()

    async def alter(identifier):
        if len(review.state.calls) == 1:
            async with primary_authority(read_only=False):
                await review.records._require_session().execute(
                    update(SourceMapping).where(SourceMapping.id == first.id).values(revision=2)
                )

    review.state.during = alter
    with pytest.raises(SourceError, match="authority_changed"):
        await review.service.review("issuer|alice", "tenant", review.request)
    assert len(await rows(review)) == 1


async def test_grant_changed_after_remote_confirmation_is_rechecked_under_lock(review, monkeypatch):
    original = review.service.connections.confirm_read_grant

    async def confirm(*args):
        await original(*args)
        async with primary_authority(read_only=False):
            await review.records._require_session().execute(
                update(PersonalSourceConnection)
                .where(PersonalSourceConnection.id == review.connection.id)
                .values(revision=PersonalSourceConnection.revision + 1)
            )

    monkeypatch.setattr(review.service.connections, "confirm_read_grant", confirm)
    with pytest.raises(SourceError, match="authority_changed"):
        await review.service.review("issuer|alice", "tenant", review.request)
    assert await rows(review) == []


async def test_cancelled_review_saves_nothing_and_releases_reader_slot(review):
    entered = asyncio.Event()
    blocked = asyncio.Event()

    async def wait(identifier):
        entered.set()
        await blocked.wait()

    review.state.during = wait
    task = asyncio.create_task(review.service.review("issuer|alice", "tenant", review.request))
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await rows(review) == []
    review.state.during = None
    result = await review.service.review("issuer|alice", "tenant", review.request)
    assert result.status == "reviewed"


async def test_candidate_guardrail_rejects_before_network_without_truncation(review):
    await review.service.review("issuer|alice", "tenant", review.request)
    stored = (await rows(review))[0]
    values = {column.name: getattr(stored, column.name) for column in SourceMapping.__table__.columns}
    async with primary_authority(read_only=False):
        session = review.records._require_session()
        for index in range(99):
            session.add(SourceMapping(**(values | {"id": f"candidate-{index}"})))
        await session.flush()
    review.state.calls.clear()
    with pytest.raises(SourceError, match="size_exceeded"):
        await review.service.review("issuer|alice", "tenant", review.request)
    assert review.state.calls == [] and len(await rows(review)) == 100
