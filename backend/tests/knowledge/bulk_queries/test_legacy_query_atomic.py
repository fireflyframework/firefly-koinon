# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4


async def test_compatibility_query_lookup_cannot_split_marker_and_business_row_snapshots():
    from koinon.knowledge.legacy_read import LegacyReadAdmission

    # A marker absent before commit must not authorize a row visible after that commit.
    guard = object.__new__(LegacyReadAdmission)
    reads = SimpleNamespace(
        assert_legacy_query_unmarked=AsyncMock(), legacy_query_metadata=AsyncMock(return_value=None)
    )

    def separate_snapshot(*_):
        raise AssertionError("A query marker check and generic metadata read must be one native statement")

    guard.query_reads = reads
    guard.datasources = SimpleNamespace(get=separate_snapshot)
    query, workspace = uuid4(), uuid4()
    assert await guard._lookup("structured", "query", str(query), "north", str(workspace)) is None
    reads.assert_legacy_query_unmarked.assert_not_awaited()
    reads.legacy_query_metadata.assert_awaited_once_with(query, "north", workspace)
