# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Browser lifetime follows product defaults and the native persisted deadline."""

import os
import runpy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from pyfly.security.context import SecurityContext
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
    database = "browser_lifetime_" + uuid4().hex[:12]
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
    try:
        yield
    finally:
        with psycopg.connect(uri, autocommit=True) as owner:
            owner.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


@pytest.fixture
def shorter_lifetime(monkeypatch, owned_postgres_session):
    import koinon.app

    original = koinon.app.create_application

    def configured(values):
        values["pyfly"]["session"] = {"ttl": 300}
        return original(values)

    monkeypatch.setattr(koinon.app, "create_application", configured)


def assert_new_session_lifetime(client, monkeypatch, seconds):
    store = client.native_app.state.context.get_bean(SessionStore)
    assert isinstance(store, SqlSessionStore)
    now = datetime(2026, 11, 10, 12, tzinfo=UTC)
    monkeypatch.setattr(store, "_clock", lambda: now)
    response = client.get("/oauth2/authorization/koinon", follow_redirects=False)
    assert response.status_code == 302
    session_id = response.cookies["PYFLY_SESSION"]
    assert f"Max-Age={seconds};" in response.headers["set-cookie"]
    assert client.portal.call(store.expires_at, session_id) == now + timedelta(seconds=seconds)
    assert client.portal.call(store.get, session_id)["oauth2_state"]


def test_default_browser_session_lasts_eight_hours(client, monkeypatch):
    assert_new_session_lifetime(client, monkeypatch, 28800)


@pytest.mark.usefixtures("shorter_lifetime")
def test_explicit_shorter_browser_lifetime_wins(client, monkeypatch):
    assert_new_session_lifetime(client, monkeypatch, 300)


def test_reading_session_does_not_extend_old_deadline_even_when_cookie_is_reissued(client, monkeypatch):
    store = client.native_app.state.context.get_bean(SessionStore)
    now = datetime(2026, 11, 10, 12, tzinfo=UTC)
    monkeypatch.setattr(store, "_clock", lambda: now)
    deadline = now + timedelta(seconds=60)
    identity = SecurityContext(
        user_id="admin", attributes={"iss": _fixtures["ISSUER"], "sub": "admin"}
    )
    client.portal.call(store.save, "old-short-session", {"SECURITY_CONTEXT": identity}, 60)
    client.cookies.set("PYFLY_SESSION", "old-short-session", domain="testserver.local", path="/")
    for elapsed in (0, 30):
        now = deadline - timedelta(seconds=60 - elapsed)
        response = client.get("/auth/me")
        assert response.status_code == 200
        assert response.json()["expires_at"] == deadline.isoformat().replace("+00:00", "Z")
        assert "Max-Age=28800;" in response.headers["set-cookie"]
        assert client.portal.call(store.expires_at, "old-short-session") == deadline
    now = deadline + timedelta(seconds=1)
    assert client.get("/auth/me").status_code == 401
    assert client.portal.call(store.get, "old-short-session") is None


def test_logout_revokes_session_before_its_eight_hour_deadline(client):
    store = client.native_app.state.context.get_bean(SessionStore)
    identity = SecurityContext(
        user_id="admin", attributes={"iss": _fixtures["ISSUER"], "sub": "admin"}
    )
    client.portal.call(store.save, "logout-session", {"SECURITY_CONTEXT": identity}, 28800)
    client.cookies.set("PYFLY_SESSION", "logout-session", domain="testserver.local", path="/")
    assert client.get("/auth/me").status_code == 200
    assert client.post("/logout").status_code == 403
    response = client.post(
        "/logout", headers={"X-XSRF-TOKEN": client.cookies["XSRF-TOKEN"]}, follow_redirects=False
    )
    assert response.status_code == 302
    assert client.portal.call(store.get, "logout-session") is None
    client.cookies.set("PYFLY_SESSION", "logout-session", domain="testserver.local", path="/")
    assert client.get("/auth/me").status_code == 401
