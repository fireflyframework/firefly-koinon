# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exercise the shared nested-folder SQL path on an explicitly owned PostgreSQL fixture."""

import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url
from test_query_service import (
    test_nested_dataset_history_uses_complete_active_ancestry_before_count as nested_history,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def query_url():
    value = os.environ.get("KOINON_TEST_BULK_POSTGRES_URL")
    if not value:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    url = make_url(value)
    assert url.host == "127.0.0.1" and url.port != 18783
    name = "nested_query_" + uuid4().hex
    with psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    print(f"Retained owned PostgreSQL database: {name}; nested query history")
    return url.set(drivername="postgresql+asyncpg", database=name).render_as_string(hide_password=False)


async def test_nested_dataset_history_postgres(queries):
    await nested_history(queries)
