# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock

import pytest
from test_availability_batch import (
    test_after_native_read_rechecks_current_authority as assert_current_authority,
)
from test_availability_batch import (
    test_availability_and_processing_batch_primary_reads as assert_query_budget,
)
from test_search_batch_postgres import postgres_context as postgres_context

pytestmark = pytest.mark.integration


def upload_adapter(context):
    domains = context[2]
    domains.ensure_workspace = AsyncMock(return_value="native-workspace")
    domains.ingest_document = AsyncMock(return_value={"source_id": "native-source", "n_chunks": 2})


async def test_postgres_availability_and_processing_batch_queries(postgres_context, record_property):
    upload_adapter(postgres_context)
    counts = await assert_query_budget(postgres_context, record_property)
    assert counts["observe"] == [14, 14]


@pytest.mark.parametrize("change", ["membership", "ancestor", "foreign_parent"])
async def test_postgres_after_native_read_rechecks_authority(postgres_context, change):
    upload_adapter(postgres_context)
    await assert_current_authority(postgres_context, change)
