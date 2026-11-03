# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product HTTP callbacks consume their native PostgreSQL challenge before provider I/O."""

import asyncio
import os
import runpy
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

import jwt
import psycopg
import pytest
from psycopg import sql
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import current_unit_of_work
from pyfly.security.oauth2.login import OAuth2LoginHandler
from pyfly.session.adapters.sql_session_store import SqlSessionStore
from pyfly.session.ports.outbound import SessionStore
from sqlalchemy.engine import make_url

_fixtures = runpy.run_path(str(Path(__file__).parents[1] / "web" / "conftest.py"))
client = _fixtures["client"]
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def owned_postgres_session(monkeypatch):
    uri = os.environ.get("KOINON_MEMORY_AUTHORITY_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    url = make_url(uri)
    assert url.host == "127.0.0.1" and url.port != 18783
    database = "session_claim_" + uuid4().hex[:12]
    with psycopg.connect(uri, autocommit=True) as owner:
        owner.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    import koinon.app

    original = koinon.app.create_application

    def configured(values):
        values["pyfly"]["data"]["relational"]["url"] = url.set(
            drivername="postgresql+asyncpg", database=database
        ).render_as_string(hide_password=False)
        return original(values)

    monkeypatch.setattr(koinon.app, "create_application", configured)


def test_product_postgres_callback_claim_allows_only_one_exchange_and_retires_old_cookie(client, monkeypatch):
    context = client.native_app.state.context
    store = context.get_bean(SessionStore)
    assert isinstance(store, SqlSessionStore)
    assert context.get_bean(DataSourceRegistry).primary.engine.dialect.name == "postgresql"
    login = context.get_bean(OAuth2LoginHandler)
    authorization = client.get("/oauth2/authorization/koinon", follow_redirects=False)
    assert authorization.status_code == 302
    parameters = parse_qs(urlsplit(authorization.headers["location"]).query)
    original_id = authorization.cookies["PYFLY_SESSION"]
    snapshot = client.portal.call(store.get, original_id)
    assert snapshot["oauth2_state"] == parameters["state"][0]
    started, release = Event(), Event()
    exchanges = []

    async def exchange(registration, code, code_verifier=None):
        assert current_unit_of_work("primary") is None
        assert await store.get(original_id) is None
        assert code_verifier == snapshot["oauth2_pkce_verifier"]
        exchanges.append(code)
        started.set()
        assert await asyncio.to_thread(release.wait, 10)
        return {
            "access_token": "owned-test-access",
            "id_token": jwt.encode(
                {
                    "iss": _fixtures["ISSUER"],
                    "sub": "admin",
                    "aud": "browser",
                    "nonce": parameters["nonce"][0],
                    "exp": int(time.time()) + 300,
                },
                _fixtures["KEY"],
                algorithm="RS256",
                headers={"kid": "local-key"},
            ),
        }

    monkeypatch.setattr(login, "_exchange_code", exchange)
    query = urlencode({"state": parameters["state"][0], "code": "owned-code", "iss": _fixtures["ISSUER"]})
    path = "/login/oauth2/code/koinon?" + query
    headers = {"cookie": "PYFLY_SESSION=" + original_id}
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(client.get, path, headers=headers, follow_redirects=False)
        try:
            assert started.wait(10)
            duplicate = executor.submit(client.get, path, headers=headers, follow_redirects=False)
            assert duplicate.result(timeout=10).status_code == 400
        finally:
            release.set()
        completed = first.result(timeout=10)
    assert completed.status_code == 302
    assert exchanges == ["owned-code"]
    assert client.portal.call(store.get, original_id) is None
    authenticated_id = completed.cookies["PYFLY_SESSION"]
    assert authenticated_id != original_id
    persisted = client.portal.call(store.get, authenticated_id)
    assert persisted["SECURITY_CONTEXT"].user_id == "admin"
    assert persisted["_authenticated_at"] > 0
    assert "oauth2_state" not in persisted and "oauth2_pkce_verifier" not in persisted
    assert client.get(path, headers=headers, follow_redirects=False).status_code == 400
    assert exchanges == ["owned-code"]
