# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The actual bulk origin guard uses a fresh primary PostgreSQL policy snapshot."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_bulk_ingestion_authority as cases
from psycopg import sql
from sqlalchemy.engine import make_url
from test_bulk_ingestion_authority import captured as captured
from test_bulk_ingestion_authority import client as client
from test_bulk_ingestion_authority import knowledge_core as knowledge_core

test_bulk_origin = cases.test_bulk_origin_reaches_real_ingestion_capture_without_borrowing_ambient_identity
test_bulk_revocation = cases.test_bulk_reconstructed_origin_still_denies_current_revocation
test_bulk_queue_recheck = cases.test_queue_recheck_preserves_origin_for_actual_native_policy

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def owned_postgres_primary(monkeypatch):
    uri = os.environ.get("KOINON_TEST_BULK_POSTGRES_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    url = make_url(uri)
    socket = Path(url.query.get("host", ""))
    assert (url.host == "127.0.0.1" and url.port != 18783) or (
        str(socket).startswith("/tmp/koinon-bulk-pg-")
        and socket.is_dir()
        and socket.stat().st_mode & 0o077 == 0
    )
    database = "bulk_origin_" + uuid4().hex[:12]
    with psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
    ) as owner:
        owner.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    primary = url.set(drivername="postgresql+asyncpg", database=database).render_as_string(
        hide_password=False
    )
    import koinon.app

    original = koinon.app.create_application

    def configured(values):
        values["koinon"]["knowledge"]["enabled"] = True
        values["pyfly"]["data"]["relational"]["url"] = primary
        return original(values)

    monkeypatch.setattr(koinon.app, "create_application", configured)
