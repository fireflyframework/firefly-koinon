# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual PostgreSQL tenant fences between nested destination publication and Catalog mutation."""

import asyncio

import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.kernel import ConflictException
from sqlalchemy import text
from test_bulk_native import bulk as bulk
from test_bulk_native import request
from test_bulk_pinned_postgres import bulk_schema_migrated as bulk_schema_migrated
from test_bulk_pinned_postgres import bulk_url as bulk_url
from test_bulk_queue import queued
from test_nested_destinations import nested

from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.catalog.hierarchy_service import CatalogHierarchyService
from koinon.knowledge.bulk.queue import BulkQueue
from koinon.security.authority import primary_authority

pytestmark = pytest.mark.integration


async def waiting_on_postgres_lock(bulk):
    engine = bulk.context.get_bean(DataSourceRegistry).get("primary").engine
    async with asyncio.timeout(10):
        while True:
            async with engine.connect() as connection:
                waiting = await connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                        "AND wait_event_type='Lock' AND cardinality(pg_blocking_pids(pid))>0"
                    )
                )
            if waiting:
                return
            await asyncio.sleep(0.01)


async def drain(tasks, release):
    release.set()
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize("first", ["archive", "publication"])
async def test_nested_worker_and_ancestor_mutation_serialize_without_publication_escape(bulk, first):
    original = dict(bulk.target)
    bulk.target = await nested(bulk)
    sibling = await bulk.catalog.create(
        "issuer|editor", "north", kind="collection", name="Sibling", parent_id=original["project_id"]
    )
    await queued(bulk, "nested-lock")
    queue = bulk.context.get_bean(BulkQueue)
    lease = await queue.claim("nested-worker")
    ancestor = await bulk.catalog.get("issuer|editor", "north", original["parent_id"])
    held, release = asyncio.Event(), asyncio.Event()
    published = []

    async def archive_first():
        async with primary_authority(read_only=False):
            await bulk.catalog.archive("issuer|editor", "north", ancestor.id)
            held.set()
            await release.wait()

    async def publish():
        async with queue.publication(lease):
            assert lease.destination.parent_id == bulk.target["parent_id"]
            if first == "publication":
                held.set()
                await release.wait()
            published.append(lease.item_id)

    async def move():
        return await CatalogHierarchyService(bulk.catalog).move(
            "issuer|editor",
            "north",
            ancestor.id,
            parent_id=sibling.id,
            expected_parent_id=ancestor.parent_id,
            expected_updated_at=ancestor.updated_at,
        )

    tasks = [asyncio.create_task(archive_first() if first == "archive" else publish())]
    try:
        await asyncio.wait_for(held.wait(), 10)
        tasks.append(asyncio.create_task(publish() if first == "archive" else move()))
        await waiting_on_postgres_lock(bulk)
        assert not tasks[1].done()
        release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)
        assert results[0] is None
        if first == "archive":
            assert isinstance(results[1], (AccessDenied, InvalidHierarchy)) and published == []
        else:
            assert isinstance(results[1], ConflictException) and results[1].code == "FOLDER_BUSY"
            assert published == [lease.item_id]
        engine = bulk.context.get_bean(DataSourceRegistry).get("primary").engine
        print(f"Retained owned PostgreSQL database: {engine.url.database}; order={first}")
    finally:
        await drain(tasks, release)


async def test_committed_parent_move_before_admission_uses_fresh_ancestry_without_retargeting(bulk):
    target = await nested(bulk)
    ancestor = await bulk.catalog.get("issuer|editor", "north", bulk.target["parent_id"])
    sibling = await bulk.catalog.create(
        "issuer|editor", "north", kind="collection", name="Sibling", parent_id=bulk.target["project_id"]
    )
    held, release = asyncio.Event(), asyncio.Event()

    async def move():
        async with primary_authority(read_only=False):
            await CatalogHierarchyService(bulk.catalog).move(
                "issuer|editor",
                "north",
                ancestor.id,
                parent_id=sibling.id,
                expected_parent_id=ancestor.parent_id,
                expected_updated_at=ancestor.updated_at,
            )
            held.set()
            await release.wait()

    tasks = [asyncio.create_task(move())]
    try:
        await asyncio.wait_for(held.wait(), 10)
        tasks.append(
            asyncio.create_task(bulk.service.create("issuer|editor", "north", request(target), "after-move"))
        )
        await waiting_on_postgres_lock(bulk)
        release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks), 10)
        batch = results[1]
        assert batch.destination.parent_id == target["parent_id"]
        items = await bulk.service.items("issuer|editor", "north", batch.id)
        source = await bulk.catalog.get("issuer|editor", "north", items.items[0].source_id)
        assert source.parent_id == target["parent_id"] and source.project_id == target["project_id"]
        page = await bulk.service.list("issuer|editor", "north")
        assert page.total == 1 and page.items[0].id == batch.id
        engine = bulk.context.get_bean(DataSourceRegistry).get("primary").engine
        print(f"Retained owned PostgreSQL database: {engine.url.database}; order=move-before-admission")
    finally:
        await drain(tasks, release)
