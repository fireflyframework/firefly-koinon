# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real native units around controlled provider I/O, including late-write races."""

import base64
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlsplit

import pytest
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.transaction import current_unit_of_work
from pyfly.oauth2 import OAuth2Tokens
from pyfly.security.context import SecurityContext
from pyfly.session.adapters.memory import InMemorySessionStore
from pyfly.session.ports.outbound import SessionStore

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.integrations.content_sources.dtos import Account
from koinon.integrations.content_sources.errors import SourceError


@pytest.fixture
async def lifecycle(tmp_path, monkeypatch):
    from koinon.integrations.content_sources.lifecycle import SourceConnectionService
    from koinon.integrations.content_sources.settings import ContentSourceSettings

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'connections.db'}",
                        }
                    },
                }
            }
        )
    )
    sessions = InMemorySessionStore()
    context.container.register_instance(SessionStore, sessions)
    await sessions.save(
        "browser-a",
        {"SECURITY_CONTEXT": SecurityContext(user_id="alice", attributes={"iss": "issuer", "sub": "alice"})},
        600,
    )
    for package in ("koinon.catalog", "koinon.jobs", "koinon.integrations.content_sources"):
        scan_package(package, context.container)
    from koinon.authorized_applications.entities import AuthorizedApplication  # noqa: F401
    from koinon.knowledge.bulk.authority import BulkAuthority
    from koinon.knowledge.bulk.repositories import BulkRepository

    context.register_bean(BulkAuthority)
    context.register_bean(BulkRepository)
    await context.start()
    settings = context.get_bean(ContentSourceSettings)
    settings.master_key = base64.b64encode(bytes(range(32))).decode()
    settings.providers = {
        "google_drive": {
            "client_id": "source-client",
            "client_secret": "synthetic-secret",
            "redirect_uri": "https://app.example.test/sources/callback",
        }
    }
    await context.get_bean(TenantRepository).save(Tenant(id="tenant", name="Tenant"))
    for owner in ("issuer|alice", "issuer|bob"):
        await context.get_bean(MembershipRepository).save(
            Membership(id=owner, subject=owner, tenant_id="tenant", role="viewer")
        )
    service = context.get_bean(SourceConnectionService)
    state = {"calls": [], "during": None, "refresh": None}

    @asynccontextmanager
    async def remote(registration):
        from koinon.integrations.content_sources.oauth import ReadOnlySourceOAuth

        class Provider:
            def authorization_url(self, **kwargs):
                with_client = ReadOnlySourceOAuth(registration.config)
                return with_client.authorization_url(**kwargs)

            async def exchange_code(self, code, *, code_verifier):
                unit = current_unit_of_work("primary")
                assert unit is None or unit.completed
                state["calls"].append("exchange")
                if state["during"]:
                    await state["during"]()
                return OAuth2Tokens(
                    "access-one",
                    "Bearer",
                    3600,
                    "refresh-one",
                    "signed-id",
                    " ".join(registration.config.scopes),
                )

            async def refresh_token(self, token, *, granted_scopes):
                unit = current_unit_of_work("primary")
                assert unit is None or unit.completed
                assert token == "refresh-one"
                state["calls"].append("refresh")
                if state["refresh"]:
                    await state["refresh"]()
                return OAuth2Tokens(
                    "access-two", "Bearer", 3600, "refresh-two", None, " ".join(granted_scopes)
                )

        yield Provider()

    @asynccontextmanager
    async def identity(registration):
        class Verifier:
            issuer = "https://accounts.google.com"

            async def verify(self, token, *, nonce):
                assert token == "signed-id" and nonce
                return Account("google_drive", "verified-alice")

        yield Verifier()

    monkeypatch.setattr(service, "_oauth", remote)
    monkeypatch.setattr(service, "_identity", identity)
    try:
        yield service, settings, state, context
    finally:
        await context.stop()


async def begin(service):
    start = await service.begin("issuer|alice", "tenant", "browser-a", "google_drive")
    state = parse_qs(urlsplit(start.authorization_url).query)["state"][0]
    return start, state


async def complete(service, start, state):
    return await service.complete(
        "issuer|alice", "tenant", "browser-a", start.challenge_id, state=state, code="one-use-code"
    )


async def test_owner_session_and_one_use_code_are_fenced_before_network(lifecycle):
    service, _, calls, _ = lifecycle
    start, state = await begin(service)
    for actor, tenant, session in (
        ("issuer|bob", "tenant", "browser-a"),
        ("issuer|alice", "other", "browser-a"),
        ("issuer|alice", "tenant", "browser-b"),
    ):
        with pytest.raises((SourceError, AccessDenied)):
            await service.complete(actor, tenant, session, start.challenge_id, state=state, code="code")
    assert calls["calls"] == []
    result = await complete(service, start, state)
    assert result.status == "connected" and result.account.subject == "verified-alice"
    assert "access-one" not in repr(result) and "refresh-one" not in repr(result)
    with pytest.raises(SourceError):
        await complete(service, start, state)
    assert calls["calls"] == ["exchange"]


@pytest.mark.parametrize("change", ["logout", "owner"])
async def test_native_session_changed_during_exchange_never_persists_grant(lifecycle, change):
    service, _, calls, context = lifecycle
    start, state = await begin(service)

    async def change_session():
        sessions = context.get_bean(SessionStore)
        if change == "logout":
            await sessions.delete("browser-a")
        else:
            await sessions.save(
                "browser-a",
                {
                    "SECURITY_CONTEXT": SecurityContext(
                        user_id="bob", attributes={"iss": "issuer", "sub": "bob"}
                    )
                },
                600,
            )

    calls["during"] = change_session
    with pytest.raises(SourceError):
        await complete(service, start, state)
    assert calls["calls"] == ["exchange"]


@pytest.mark.parametrize("change", ["client_id", "client_secret", "redirect_uri", "provider"])
async def test_configuration_change_during_exchange_rejects_late_grant(lifecycle, change):
    service, settings, calls, _ = lifecycle
    start, state = await begin(service)

    async def alter():
        if change == "provider":
            settings.providers.clear()
        else:
            settings.providers["google_drive"][change] += "-changed"

    calls["during"] = alter
    with pytest.raises(SourceError):
        await complete(service, start, state)
    calls["during"] = None
    with pytest.raises(SourceError):
        await complete(service, start, state)
    assert calls["calls"] == ["exchange"]


async def test_disconnect_during_exchange_blocks_late_completion(lifecycle):
    service, _, calls, _ = lifecycle
    start, state = await begin(service)

    async def disconnect():
        await service.disconnect("issuer|alice", "tenant", start.connection_id, 1)

    calls["during"] = disconnect
    with pytest.raises(SourceError):
        await complete(service, start, state)
    assert calls["calls"] == ["exchange"]


async def test_unknown_exchange_is_not_replayed(lifecycle):
    service, _, calls, _ = lifecycle
    start, state = await begin(service)

    async def timeout():
        raise TimeoutError("Provider outcome unknown")

    calls["during"] = timeout
    with pytest.raises(SourceError):
        await complete(service, start, state)
    with pytest.raises(SourceError):
        await complete(service, start, state)
    assert calls["calls"] == ["exchange"]


@pytest.mark.parametrize("change", ["client_id", "client_secret", "provider", "disconnect", "timeout"])
async def test_refresh_rechecks_configuration_and_revision_without_replay(lifecycle, change):
    from koinon.integrations.content_sources.repositories import SourceConnectionRepository
    from koinon.security.authority import primary_authority

    service, settings, calls, context = lifecycle
    start, state = await begin(service)
    connected = await complete(service, start, state)

    async def alter():
        if change == "provider":
            settings.providers.clear()
        elif change == "disconnect":
            await service.disconnect("issuer|alice", "tenant", start.connection_id, connected.revision)
        elif change == "timeout":
            raise TimeoutError("Provider outcome unknown")
        else:
            settings.providers["google_drive"][change] += "-changed"

    calls["refresh"] = alter
    async with primary_authority(read_only=False):
        row = await context.get_bean(SourceConnectionRepository).owned(
            "tenant", "issuer|alice", start.connection_id
        )
        payload = service.vault.decrypt("tenant", "issuer|alice", row.id, "grant", row.secret_ciphertext)
        payload["expires_at"] = 0
        row.secret_ciphertext = service.vault.encrypt("tenant", "issuer|alice", row.id, "grant", payload)
        await context.get_bean(SourceConnectionRepository).save(row)
    with pytest.raises(SourceError):
        await service.access_token("issuer|alice", "tenant", start.connection_id, connected.account)
    with pytest.raises(SourceError):
        await service.access_token("issuer|alice", "tenant", start.connection_id, connected.account)
    assert calls["calls"] == ["exchange", "refresh"]


async def test_rotation_persists_new_grant_and_other_readers_cannot_borrow_it(lifecycle):
    from koinon.integrations.content_sources.repositories import SourceConnectionRepository
    from koinon.security.authority import primary_authority

    service, _, calls, context = lifecycle
    start, state = await begin(service)
    connected = await complete(service, start, state)
    for actor, tenant, account in (
        ("issuer|bob", "tenant", connected.account),
        ("issuer|alice", "other", connected.account),
        ("issuer|alice", "tenant", Account("google_drive", "other-external-subject")),
    ):
        with pytest.raises((SourceError, AccessDenied)):
            await service.access_token(actor, tenant, start.connection_id, account)
    assert (
        await service.access_token("issuer|alice", "tenant", start.connection_id, connected.account)
        == "access-one"
    )
    async with primary_authority(read_only=False):
        row = await context.get_bean(SourceConnectionRepository).owned(
            "tenant", "issuer|alice", start.connection_id
        )
        grant = service.vault.decrypt("tenant", "issuer|alice", row.id, "grant", row.secret_ciphertext)
        grant["expires_at"] = 0
        row.secret_ciphertext = service.vault.encrypt("tenant", "issuer|alice", row.id, "grant", grant)
        await context.get_bean(SourceConnectionRepository).save(row)
    assert (
        await service.access_token("issuer|alice", "tenant", start.connection_id, connected.account)
        == "access-two"
    )
    assert (
        await service.access_token("issuer|alice", "tenant", start.connection_id, connected.account)
        == "access-two"
    )
    assert calls["calls"] == ["exchange", "refresh"]
    async with primary_authority():
        row = await context.get_bean(SourceConnectionRepository).owned(
            "tenant", "issuer|alice", start.connection_id
        )
        grant = service.vault.decrypt("tenant", "issuer|alice", row.id, "grant", row.secret_ciphertext)
        assert grant["refresh_token"] == "refresh-two" and row.revision == connected.revision + 1


async def test_revoked_tenant_access_during_exchange_cannot_publish_grant(lifecycle):
    service, _, calls, context = lifecycle
    start, state = await begin(service)

    async def revoke():
        rows = context.get_bean(MembershipRepository)
        row = await rows.find_by_id("issuer|alice")
        row.active = False
        await rows.save(row)

    calls["during"] = revoke
    with pytest.raises(AccessDenied):
        await complete(service, start, state)
    assert calls["calls"] == ["exchange"]


async def test_narrowed_scopes_are_persisted_for_the_next_refresh(lifecycle, monkeypatch):
    import httpx
    from pyfly.oauth2 import OAuth2Client, OAuth2Endpoints

    from koinon.integrations.content_sources.oauth import ReadOnlySourceOAuth
    from koinon.integrations.content_sources.repositories import SourceConnectionRepository
    from koinon.security.authority import primary_authority

    service, _, _, context = lifecycle
    start, state = await begin(service)
    connected = await complete(service, start, state)
    requests = []
    read_scope = "https://www.googleapis.com/auth/drive.readonly"

    def response(request):
        values = parse_qs(request.content.decode())
        requests.append(values)
        return httpx.Response(
            200,
            json={
                "access_token": "new-access",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "rotated-" + str(len(requests)),
                "scope": read_scope,
            },
        )

    @asynccontextmanager
    async def native(registration):
        async with (
            OAuth2Client(
                registration.config.client_id,
                OAuth2Endpoints(registration.config.token_endpoint),
                transport=httpx.MockTransport(response),
            ) as client,
            ReadOnlySourceOAuth(registration.config, client=client) as oauth,
        ):
            yield oauth

    monkeypatch.setattr(service, "_oauth", native)
    for _ in range(2):
        async with primary_authority(read_only=False):
            row = await context.get_bean(SourceConnectionRepository).owned(
                "tenant", "issuer|alice", start.connection_id
            )
            grant = service.vault.decrypt("tenant", "issuer|alice", row.id, "grant", row.secret_ciphertext)
            grant["expires_at"] = 0
            row.secret_ciphertext = service.vault.encrypt("tenant", "issuer|alice", row.id, "grant", grant)
            await context.get_bean(SourceConnectionRepository).save(row)
        await service.access_token("issuer|alice", "tenant", start.connection_id, connected.account)
    assert len(requests) == 2
    assert requests[1]["scope"] == [read_scope]
    assert requests[1]["refresh_token"] == ["rotated-1"]


async def test_workspace_only_reader_can_own_a_personal_connection_without_tenant_wide_grants(lifecycle):
    from koinon.catalog.entities import CatalogEntry
    from koinon.catalog.repositories import CatalogRepository

    service, _, _, context = lifecycle
    await context.get_bean(CatalogRepository).save(
        CatalogEntry(
            id="permitted-space",
            tenant_id="tenant",
            workspace_id="permitted-space",
            kind="workspace",
            name="Existing authorized space",
            created_by="issuer|alice",
            updated_by="issuer|alice",
        )
    )
    rows = context.get_bean(MembershipRepository)
    membership = await rows.find_by_id("issuer|alice")
    membership.workspace_id = "permitted-space"
    await rows.save(membership)
    start, state = await begin(service)
    connected = await complete(service, start, state)
    assert connected.status == "connected"
    assert (await rows.find_by_id("issuer|alice")).workspace_id == "permitted-space"
    assert len(await rows.find_all(subject="issuer|alice")) == 1
