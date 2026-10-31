# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import sqlite3

import pytest
from test_curated_intents import curated as curated
from test_curated_native_events import native_lifecycle as native_lifecycle
from test_curated_release_fence import _two_workspace_case


@pytest.mark.parametrize("operation", ["whole", "search"])
async def test_primary_revocation_denies_body(curated, native_lifecycle, tmp_path, operation):
    from pyfly.data.relational.datasource_registry import DataSource
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.curated.whole import CuratedWholeVersionReader

    reads, corpus, selected, published, primary = await _two_workspace_case(curated, native_lifecycle)
    reader = curated[3].get_bean(CuratedWholeVersionReader)
    meta = await reader.pin("issuer|reader", "north", "owned", selected[0])
    replica_path = tmp_path / "lagging-policy.db"
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
    try:

        async def revoke():
            async with primary.engine.begin() as connection:
                await connection.execute(
                    update(Membership).where(Membership.subject == "issuer|reader").values(active=False)
                )

        if operation == "whole":
            original = reader.parts.read

            async def read_then_revoke(*args, **kwargs):
                value = await original(*args, **kwargs)
                await revoke()
                return value

            reader.parts.read = read_then_revoke
        else:
            original = corpus.ranked

            async def ranked_then_revoke(*args, **kwargs):
                value = await original(*args, **kwargs)
                await revoke()
                return value

            corpus.ranked = ranked_then_revoke
        with pytest.raises(AccessDenied):
            if operation == "whole":
                value = await reader.read("issuer|reader", "north", meta)
                assert "47" in value.text
            else:
                value = await corpus.search(
                    "issuer|reader", "north", "owned", selected, query="threshold", limit=10
                )
                assert value
    finally:
        primary.replica = None
        await engine.dispose()
