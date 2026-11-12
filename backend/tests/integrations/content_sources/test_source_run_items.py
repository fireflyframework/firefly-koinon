# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Run history reveals only freshly authorized candidates, including empty visible pages."""

from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from sqlalchemy import delete, select
from test_sync_publication_service import empty_listing as empty_listing
from test_sync_publication_service import lifecycle as lifecycle
from test_sync_publication_service import producer as producer
from test_sync_publication_service import review as review
from test_sync_publication_service import source_database as source_database

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.mapping_entities import SourceObject
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.sync_checkpoints import SourceCheckpoints
from koinon.integrations.content_sources.sync_entities import SourceSyncWork
from koinon.integrations.content_sources.sync_walk import WalkItem, WalkPage
from koinon.security.authority import primary_authority

pytestmark = [
    pytest.mark.integration,
    pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True),
    pytest.mark.parametrize("producer", ["folder"], indirect=True),
]


@pytest.fixture
async def history(producer, monkeypatch):
    value = producer
    files = tuple(
        replace(value.remote_item, item_id=identifier, name=identifier + ".txt", kind="file")
        for identifier in ("visible", "hidden")
    )
    value.changed["items"].update({item.item_id: item for item in files})
    async with primary_authority(read_only=False):
        await SourceCheckpoints(session=value.guard._require_session()).append(
            value.execution,
            1,
            WalkPage(tuple(WalkItem(item, ("selected",)) for item in files), None, True, len(files)),
            cursor_ciphertext=None,
        )
    service = value.review.context.get_bean(SourceMappings)
    original = service.browser._source
    denied, checks = {}, []

    @asynccontextmanager
    async def remote(scope, tokens):
        async with original(scope, tokens) as adapter:
            get_item = adapter.get_item

            async def get(identifier):
                _no_remote_unit()
                checks.append(identifier)
                if identifier in denied:
                    raise denied[identifier]
                return await get_item(identifier)

            adapter.get_item = get
            yield adapter

    monkeypatch.setattr(service.browser, "_source", remote)
    value.status_service, value.denied, value.status_checks = service, denied, checks
    return value


async def test_run_items_omit_denials_without_hydrating_historical_payload(history, monkeypatch):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import event

    value = history
    value.denied["hidden"] = SourceError("access_denied")
    engine = value.review.context.get_bean(DataSourceRegistry).primary.engine.sync_engine

    def no_payload(connection, cursor, statement, parameters, context, many):
        assert "koinon_content_sync_observations.event_json" not in statement

    event.listen(engine, "before_cursor_execute", no_payload)
    try:
        page = await value.status_service.run_items("issuer|alice", "tenant", value.admission.run_id)
    finally:
        event.remove(engine, "before_cursor_execute", no_payload)
    assert {item.name for item in page.items} == {"Finance", "visible.txt"}
    assert "total" not in page.model_dump() and page.next_cursor is None
    assert all(item.status == "observed" for item in page.items)
    assert all(item.relative_path == [item.name] for item in page.items)


async def test_denied_candidate_pages_preserve_continuation_without_exposing_identifiers(history):
    value = history
    value.denied.update(
        {
            identifier: SourceError("unavailable", definitive_read_denial=True)
            for identifier in ("file", "visible", "hidden")
        }
    )
    cursor, pages = None, []
    for _ in range(3):
        page = await value.status_service.run_items(
            "issuer|alice", "tenant", value.admission.run_id, cursor=cursor, limit=1
        )
        assert page.items == [] and set(page.model_dump()) == {"items", "next_cursor"}
        pages.append(page)
        cursor = page.next_cursor
    assert pages[0].next_cursor and pages[1].next_cursor and pages[2].next_cursor is None
    with pytest.raises(SourceError):
        await value.status_service.run_items(
            "issuer|bob", "tenant", value.admission.run_id, cursor=pages[0].next_cursor, limit=1
        )


@pytest.mark.parametrize("code", ["timeout", "throttled", "unavailable", "transport_error"])
async def test_indeterminate_provider_failure_is_not_an_empty_success(history, code):
    history.denied["hidden"] = SourceError(code)
    with pytest.raises(SourceError):
        await history.status_service.run_items("issuer|alice", "tenant", history.admission.run_id)


async def test_post_provider_membership_revocation_withholds_the_entire_page(history, monkeypatch):
    value = history
    original = value.status_service.connections.confirm_read_grant

    async def revoke(*args, **kwargs):
        await original(*args, **kwargs)
        async with primary_authority(read_only=False):
            await value.guard._require_session().execute(
                delete(Membership).where(Membership.id == "issuer|alice")
            )

    monkeypatch.setattr(value.status_service.connections, "confirm_read_grant", revoke)
    with pytest.raises((SourceError, AccessDenied)):
        await value.status_service.run_items("issuer|alice", "tenant", value.admission.run_id)


async def test_only_the_exact_published_folder_generation_is_synchronized(history):
    from koinon.integrations.content_sources.sync_folders import SourceFolders

    value = history
    await SourceFolders(value.writer).publish(value.admission, value.execution)
    page = await value.status_service.run_items("issuer|alice", "tenant", value.admission.run_id)
    folder = next(item for item in page.items if item.kind == "folder")
    assert folder.status == "synchronized"
    value.changed["version"] = "new-remote-version"
    with pytest.raises(SourceError):
        await value.status_service.run_items("issuer|alice", "tenant", value.admission.run_id)
    async with primary_authority():
        session = value.guard._require_session()
        assert (await session.get(SourceObject, folder.object_id)).remote_version == "v1"
        assert (
            await session.scalar(select(SourceSyncWork).where(SourceSyncWork.id == folder.id))
        ).status == "imported"
