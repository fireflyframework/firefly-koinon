# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retained file metadata cannot use an obsolete replica membership grant."""

import sqlite3

import pytest
from pyfly.data.relational.datasource_registry import DataSource, DataSourceRegistry
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_bulk_native import bulk as bulk
from test_bulk_native import request

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied


@pytest.mark.parametrize("operation", ["get", "items", "list", "capabilities", "receipt"])
async def test_primary_membership_revocation_blocks_private_file_outputs(bulk, tmp_path, operation):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "replica-proof")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    if operation == "receipt":
        await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    registry = bulk.context.get_bean(DataSourceRegistry)
    primary = registry.get("primary")
    replica_path = tmp_path / "lagging-policy.db"
    with sqlite3.connect(primary.engine.url.database) as original, sqlite3.connect(replica_path) as backup:
        original.backup(backup)
    replica_engine = create_async_engine("sqlite+aiosqlite:///" + str(replica_path))
    primary.replica = DataSource(
        "primary",
        replica_engine,
        async_sessionmaker(replica_engine),
        properties=primary.properties,
        registry=registry,
        is_replica=True,
    )
    try:
        async with primary.engine.begin() as connection:
            await connection.execute(update(Membership).where(Membership.id == "editor").values(active=False))
        arguments = ("issuer|editor", "north")
        if operation == "capabilities":
            arguments += (bulk.target["workspace_id"],)
        elif operation != "list":
            arguments += (batch.id,)
        if operation == "receipt":
            arguments += (item.id,)
        with pytest.raises(AccessDenied):
            await getattr(bulk.service, operation)(*arguments)
    finally:
        primary.replica = None
        await replica_engine.dispose()
