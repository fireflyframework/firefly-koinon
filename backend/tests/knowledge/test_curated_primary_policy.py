# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Current curated RAG must authorize every fixed input in one primary release cut."""

import sqlite3

import pytest
from test_curated_intents import curated as curated
from test_curated_native_events import native_lifecycle as native_lifecycle
from test_curated_release_fence import _two_workspace_case


@pytest.mark.parametrize("swap", ["disjoint", "policy_aba"])
async def test_all_admitted_items_share_one_current_policy_cut(curated, native_lifecycle, swap):
    from sqlalchemy import update

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied

    _, corpus, selected, _, primary = await _two_workspace_case(curated, native_lifecycle)

    async def grants(first, second):
        async with primary.engine.begin() as connection:
            await connection.execute(
                update(Membership).where(Membership.id == "reader-0").values(active=first)
            )
            await connection.execute(
                update(Membership).where(Membership.id == "reader-1").values(active=second)
            )

    await grants(True, False)
    original_validate = corpus._validate_release

    async def validate_then_swap(subject, tenant, workspace, values):
        value = await original_validate(subject, tenant, workspace, values)
        if values[-1].item_id == selected[0].item_id:
            await grants(False, True)
        else:
            await grants(True, False)
        return value

    corpus._validate_release = validate_then_swap
    if swap == "policy_aba":
        original_observe = corpus.release.observe
        calls = 0

        async def observe_then_grant(*args, **kwargs):
            nonlocal calls
            value = await original_observe(*args, **kwargs)
            calls += 1
            if calls == 1:
                await grants(True, True)
            return value

        corpus.release.observe = observe_then_grant

        async def validate_then_restore(*args, **kwargs):
            value = await original_validate(*args, **kwargs)
            if args[-1][-1].item_id == selected[-1].item_id:
                await grants(True, False)
            return value

        corpus._validate_release = validate_then_restore

    with pytest.raises(AccessDenied):
        await corpus.authorize_release("issuer|reader", "north", selected)


async def test_archived_destination_after_native_query_cannot_use_stale_replica(
    curated, native_lifecycle, tmp_path
):
    from pyfly.data.relational.datasource_registry import DataSource
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from koinon.catalog.entities import CatalogEntry
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt

    _, corpus, selected, _, primary = await _two_workspace_case(curated, native_lifecycle)
    replica_path = tmp_path / "stale-rag-authority.db"
    with sqlite3.connect(primary.engine.url.database) as original, sqlite3.connect(replica_path) as backup:
        original.backup(backup)
    engine = create_async_engine("sqlite+aiosqlite:///" + str(replica_path))
    primary.replica = DataSource(
        "primary",
        engine,
        async_sessionmaker(engine),
        properties=primary.properties,
        registry=primary.registry,
        is_replica=True,
    )
    ranked = corpus.ranked

    async def ranked_then_archive(*args, **kwargs):
        value = await ranked(*args, **kwargs)
        async with primary.engine.begin() as connection:
            await connection.execute(
                update(CatalogEntry).where(CatalogEntry.id == curated[2].id).values(status="archived")
            )
        return value

    corpus.ranked = ranked_then_archive
    receipt = NativeEvidenceReceipt("issuer|reader", "north")
    try:
        with pytest.raises(AccessDenied):
            hits = await corpus.search(
                "issuer|reader", "north", "owned", selected, query="threshold", limit=10, _capture=receipt
            )
            assert hits and any("47" in hit.content for hit in hits)
        assert not receipt.knowledge_sources and not receipt.native_reads
    finally:
        primary.replica = None
        await engine.dispose()
