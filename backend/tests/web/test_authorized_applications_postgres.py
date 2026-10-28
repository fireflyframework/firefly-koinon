# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opt-in owned PostgreSQL transaction and lock-order qualification."""

import asyncio
import base64
import hashlib
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import InvalidRequestException, ResourceNotFoundException, UnauthorizedException
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from koinon.authorized_applications.entities import AuthorizedApplication
from koinon.authorized_applications.repositories import AuthorizedApplicationRepository
from koinon.authorized_applications.service import AuthorizedApplicationService
from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.repositories import (
    AuditRepository,
    CatalogRepository,
    MembershipRepository,
    TenantRepository,
)
from koinon.catalog.service import CatalogService
from koinon.mcp.settings import McpSettings
from koinon.mcp_auth.entities import McpAuthorization
from koinon.mcp_auth.repositories import McpAuthorizationRepository
from koinon.mcp_auth.service import McpOAuthService
from koinon.mcp_auth.settings import McpOAuthSettings
from koinon.profiles.repositories import ProfileRepository
from koinon.profiles.service import ProfileService
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository
from koinon.tokens.service import PersonalTokenService
from koinon.tokens.settings import TokenSettings

pytestmark = pytest.mark.skipif(
    not os.getenv("KOINON_APPLICATIONS_POSTGRES_URL"), reason="dedicated owned PostgreSQL"
)

OBSERVATIONS = []
RESOURCE = "https://owned-qualification.example.invalid/mcp"
REDIRECT = "https://fictional-client.example.invalid/callback"
VERIFIER = "v" * 43


@pytest.fixture
async def pg_applications(monkeypatch):
    from pyfly.agentic.models import ModelFactory

    url = os.environ["KOINON_APPLICATIONS_POSTGRES_URL"]
    target = make_url(url)
    if not (
        target.host == "127.0.0.1"
        and target.port == 18783
        and (target.database or "").startswith("koinon_applications_qualification_")
    ):
        pytest.fail("Application PostgreSQL tests require their dedicated fictional database")
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {"relational": {"enabled": True, "ddl-auto": "none", "url": url}},
                    "agentic": {"enabled": False},
                }
            }
        )
    )
    context.container.register_instance(McpSettings, McpSettings(enabled=True, public_url=RESOURCE))
    context.container.register_instance(
        McpOAuthSettings,
        McpOAuthSettings(
            enabled=True,
            encryption_key=Fernet.generate_key().decode(),
            clients=[
                {
                    "client_id": name,
                    "name": "Fictional " + name,
                    "redirect_uris": [REDIRECT],
                    "scopes": ["catalog:read", "knowledge:search"],
                }
                for name in ("client-one", "client-two", "client-three")
            ],
        ),
    )
    context.container.register_instance(TokenSettings, TokenSettings(max_active_applications_per_user=3))
    for bean in (
        TenantRepository,
        MembershipRepository,
        CatalogRepository,
        AuditRepository,
        CatalogService,
        ProfileRepository,
        ProfileService,
        PersonalTokenRepository,
        PersonalTokenService,
        TokenRestriction,
        AuthorizedApplicationRepository,
        AuthorizedApplicationService,
        McpAuthorizationRepository,
        McpOAuthService,
    ):
        context.register_bean(bean)
    await context.start()
    datasource = context.get_bean(DataSourceRegistry).get("primary")
    async with infrastructure_unit(datasource, read_only=True) as session:
        assert (
            await session.execute(
                text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
            )
        ).one() == (False, False)
        assert await session.scalar(text("SELECT current_database()")) == target.database
        assert (
            await session.scalar(text("SELECT version_num FROM koinon_native_version"))
            == "koinon_0016_authorized_apps"
        )
    monkeypatch.setattr(
        ModelFactory,
        "build_with_secret",
        lambda *args, **kwargs: pytest.fail("Models are forbidden in PostgreSQL application qualification"),
    )
    subject = "fictional-qualification|owner-" + uuid4().hex
    other = "fictional-qualification|other-" + uuid4().hex
    tenant = uuid4().hex
    await context.get_bean(TenantRepository).save(Tenant(id=tenant, name="Owned fictional qualification"))
    for owner in (subject, other):
        await context.get_bean(MembershipRepository).save(
            Membership(id=uuid4().hex, subject=owner, tenant_id=tenant, role="admin")
        )
    catalog = context.get_bean(CatalogService)
    spaces = [
        await catalog.create(subject, tenant, kind="workspace", name=name) for name in ("First", "Second")
    ]
    fixture = SimpleNamespace(
        context=context,
        datasource=datasource,
        tenant=tenant,
        subject=subject,
        other=other,
        spaces=spaces,
        oauth=context.get_bean(McpOAuthService),
        applications=context.get_bean(AuthorizedApplicationService),
        tokens=context.get_bean(PersonalTokenService),
        profiles=context.get_bean(ProfileService),
    )
    try:
        yield fixture
    finally:
        await context.stop()


async def code(fixture, *, subject=None, client="client-one", workspace=None, scope="catalog:read"):
    owner = subject or fixture.subject
    params = {
        "client_id": client,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "resource": RESOURCE,
        "scope": scope,
        "code_challenge_method": "S256",
        "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest())
        .rstrip(b"=")
        .decode(),
    }
    request, _, _, _ = await fixture.oauth.begin(owner, params)
    redirect = await fixture.oauth.consent(
        owner, request, "allow", fixture.tenant, workspace or fixture.spaces[0].id
    )
    return {
        "grant_type": "authorization_code",
        "client_id": client,
        "redirect_uri": REDIRECT,
        "resource": RESOURCE,
        "code_verifier": VERIFIER,
        "code": parse_qs(urlsplit(redirect).query)["code"][0],
    }


async def connect(fixture, **values):
    return await fixture.oauth.exchange(await code(fixture, **values))


async def rows(fixture, model):
    async with infrastructure_unit(fixture.datasource, read_only=True) as session:
        return list(
            (
                await session.scalars(
                    select(model).where(model.subject.in_([fixture.subject, fixture.other]))
                )
            ).all()
        )


async def wait_blocked(fixture, waiting, holding):
    for _ in range(160):
        async with infrastructure_unit(fixture.datasource, read_only=True) as session:
            blockers = await session.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": waiting})
        if holding in blockers:
            return
        await asyncio.sleep(0.025)
    pytest.fail("The second independent PostgreSQL connection did not wait for the expected row lock")


async def transaction(fixture, operation, pids, label):
    async with infrastructure_unit(fixture.datasource) as session:
        await session.execute(text("SET LOCAL lock_timeout='8s'"))
        pids[label] = await session.scalar(text("SELECT pg_backend_pid()"))
        return await operation()


async def test_postgres_connection_is_durable_and_credential_purpose_is_private(pg_applications):
    fixture = pg_applications
    created = await connect(fixture)
    assert await fixture.oauth.canonical_bearer(created["access_token"])
    applications = await rows(fixture, AuthorizedApplication)
    credentials = await rows(fixture, PersonalToken)
    assert len(applications) == len(credentials) == 1
    assert credentials[0].purpose == "application"
    assert credentials[0].authorized_application_id == applications[0].id
    assert credentials[0].workspace_ids == [fixture.spaces[0].id]
    await fixture.applications.revoke(fixture.subject, applications[0].id)
    with pytest.raises(UnauthorizedException):
        await fixture.oauth.canonical_bearer(created["access_token"])


@pytest.mark.parametrize("action", ["revoke", "reconnect"])
async def test_postgres_authentication_and_revoke_share_a_safe_row_lock_order(
    pg_applications, monkeypatch, action
):
    fixture = pg_applications
    created = await connect(fixture)
    raw = await fixture.oauth.canonical_bearer(created["access_token"])
    application = (await rows(fixture, AuthorizedApplication))[0]
    reconnect_code = await code(fixture) if action == "reconnect" else None
    # Reset only this fictional connection's timestamps to exercise both real touch paths.
    async with infrastructure_unit(fixture.datasource) as session:
        from sqlalchemy import update

        await session.execute(
            update(PersonalToken)
            .where(PersonalToken.authorized_application_id == application.id)
            .values(last_used_at=None)
        )
        await session.execute(
            update(AuthorizedApplication)
            .where(AuthorizedApplication.id == application.id)
            .values(last_used_at=None)
        )
    touched, resume = asyncio.Event(), asyncio.Event()
    original = fixture.tokens.repository.touch

    async def pause_after_credential_touch(identifier):
        await original(identifier)
        touched.set()
        await resume.wait()

    monkeypatch.setattr(fixture.tokens.repository, "touch", pause_after_credential_touch)
    pids = {}
    authenticating = asyncio.create_task(
        transaction(
            fixture,
            lambda: fixture.tokens.authenticate(raw, purpose="application", application_id=application.id),
            pids,
            "authenticate",
        )
    )
    await asyncio.wait_for(touched.wait(), 5)
    replacement = (
        (lambda: fixture.oauth.exchange(reconnect_code))
        if reconnect_code
        else (lambda: fixture.applications.revoke(fixture.subject, application.id))
    )
    revoking = asyncio.create_task(transaction(fixture, replacement, pids, "revoke"))
    try:
        for _ in range(100):
            if "revoke" in pids:
                break
            await asyncio.sleep(0.01)
        assert pids["authenticate"] != pids["revoke"]
        await wait_blocked(fixture, pids["revoke"], pids["authenticate"])
    finally:
        resume.set()
    results = await asyncio.gather(authenticating, revoking, return_exceptions=True)
    failures = [type(result).__name__ for result in results if isinstance(result, BaseException)]
    states = []
    for result in results:
        seen = set()
        while isinstance(result, BaseException) and id(result) not in seen:
            seen.add(id(result))
            state = getattr(result, "sqlstate", None)
            if state:
                states.append(state)
            result = getattr(result, "orig", None) or result.__cause__
    OBSERVATIONS.append(
        {
            "case": "authenticate_" + action + "_lock_order",
            "independent_connections": True,
            "errors": failures,
            "sqlstates": states,
        }
    )
    assert not failures, (
        "Concurrent authentication/revocation raised: "
        + ", ".join(failures)
        + " SQLSTATE="
        + ",".join(states)
    )
    assert (
        next(row for row in await rows(fixture, AuthorizedApplication) if row.id == application.id).revoked_at
        is not None
    )
    if action == "reconnect":
        assert sum(row.revoked_at is None for row in await rows(fixture, AuthorizedApplication)) == 1


async def serialize_on_owner(fixture, monkeypatch, first_operation, second_operation, *, method="lock_owner"):
    held, release = asyncio.Event(), asyncio.Event()
    original = getattr(fixture.profiles, method)

    async def gated(*args, **kwargs):
        result = await original(*args, **kwargs)
        if asyncio.current_task().get_name() == "qualification-first" and not held.is_set():
            held.set()
            await release.wait()
        return result

    monkeypatch.setattr(fixture.profiles, method, gated)
    pids = {}
    first = asyncio.create_task(
        transaction(fixture, first_operation, pids, "first"), name="qualification-first"
    )
    await asyncio.wait_for(held.wait(), 5)
    second = asyncio.create_task(
        transaction(fixture, second_operation, pids, "second"), name="qualification-second"
    )
    try:
        for _ in range(100):
            if "second" in pids:
                break
            await asyncio.sleep(0.01)
        assert pids["first"] != pids["second"]
        await wait_blocked(fixture, pids["second"], pids["first"])
    finally:
        release.set()
    return await asyncio.gather(first, second, return_exceptions=True)


async def test_postgres_owner_lock_serializes_quota_and_rolls_back_the_denied_code(
    pg_applications, monkeypatch
):
    fixture = pg_applications
    fixture.applications.settings.max_active_applications_per_user = 1
    first_code = await code(fixture, client="client-one")
    second_code = await code(fixture, client="client-two")
    result = await serialize_on_owner(
        fixture,
        monkeypatch,
        lambda: fixture.oauth.exchange(first_code),
        lambda: fixture.oauth.exchange(second_code),
    )
    assert isinstance(result[0], dict)
    assert isinstance(result[1], InvalidRequestException)
    assert result[1].code == "APPLICATION_LIMIT_REACHED"
    applications, credentials, authorizations = (
        await rows(fixture, AuthorizedApplication),
        await rows(fixture, PersonalToken),
        await rows(fixture, McpAuthorization),
    )
    assert len(applications) == len(credentials) == 1
    assert [row.status for row in authorizations].count("used") == 1
    assert [row.status for row in authorizations].count("code") == 1
    await fixture.applications.revoke(fixture.subject, applications[0].id)
    assert isinstance(await fixture.oauth.exchange(second_code), dict)
    assert sum(row.revoked_at is None for row in await rows(fixture, AuthorizedApplication)) == 1
    OBSERVATIONS.append(
        {
            "case": "quota",
            "second_connection_waited_for_owner_lock": True,
            "active_connections": 1,
            "denied_code_reusable": True,
        }
    )


async def test_postgres_owner_lock_serializes_two_reconnects_and_exact_scope_replacement(
    pg_applications, monkeypatch
):
    fixture = pg_applications
    baseline = await connect(fixture)
    first_code = await code(fixture)
    second_code = await code(fixture, scope="catalog:read knowledge:search")
    result = await serialize_on_owner(
        fixture,
        monkeypatch,
        lambda: fixture.oauth.exchange(first_code),
        lambda: fixture.oauth.exchange(second_code),
    )
    assert all(isinstance(value, dict) for value in result)
    applications, credentials = await rows(fixture, AuthorizedApplication), await rows(fixture, PersonalToken)
    assert len(applications) == len(credentials) == 3
    active = [row for row in applications if row.revoked_at is None]
    assert len(active) == 1 and active[0].scopes == ["catalog:read", "knowledge:search"]
    assert sum(row.revoked_at is None for row in credentials) == 1
    for previous in (baseline, result[0]):
        with pytest.raises(UnauthorizedException):
            await fixture.oauth.canonical_bearer(previous["access_token"])
    assert await fixture.oauth.canonical_bearer(result[1]["access_token"])
    OBSERVATIONS.append(
        {
            "case": "reconnect",
            "second_connection_waited_for_owner_lock": True,
            "active_connections": 1,
            "revoked_previous_connections": 2,
            "exact_scope_replacement": True,
        }
    )


async def test_postgres_profile_update_and_connection_issuance_share_the_owner_lock(
    pg_applications, monkeypatch
):
    fixture = pg_applications
    params = await code(fixture)
    result = await serialize_on_owner(
        fixture,
        monkeypatch,
        lambda: fixture.profiles.update(fixture.subject, {"locale": "es-ES"}),
        lambda: fixture.oauth.exchange(params),
        method="_locked",
    )
    assert all(isinstance(value, dict) for value in result)
    assert (await fixture.profiles.get(fixture.subject))["locale"] == "es-ES"
    assert len(await rows(fixture, AuthorizedApplication)) == 1
    OBSERVATIONS.append(
        {"case": "profile_update", "connection_waited_for_profile_owner_lock": True, "locale_preserved": True}
    )


@pytest.mark.parametrize("failure_stage", ["before_credential", "after_credential_and_wrapper_payload"])
async def test_postgres_failed_exchange_rolls_back_code_replacement_grant_and_credential(
    pg_applications, monkeypatch, failure_stage
):
    fixture = pg_applications
    baseline = await connect(fixture)
    original_application = (await rows(fixture, AuthorizedApplication))[0]
    params = await code(fixture, scope="catalog:read knowledge:search")
    if failure_stage == "before_credential":
        target, name = fixture.tokens, "issue_application"
        original = target.issue_application

        async def fail(*args, **kwargs):
            raise RuntimeError("Fictional issuance failure")
    else:
        target, name = Fernet, "encrypt"
        original = Fernet.encrypt

        def fail(*args, **kwargs):
            raise RuntimeError("Fictional wrapper failure")

    monkeypatch.setattr(target, name, fail)
    with pytest.raises(RuntimeError, match="Fictional"):
        await fixture.oauth.exchange(params)
    applications, credentials = await rows(fixture, AuthorizedApplication), await rows(fixture, PersonalToken)
    assert len(applications) == len(credentials) == 1
    assert applications[0].id == original_application.id and applications[0].revoked_at is None
    assert credentials[0].revoked_at is None
    authorizations = await rows(fixture, McpAuthorization)
    matching = next(
        row for row in authorizations if row.code_hash == hashlib.sha256(params["code"].encode()).hexdigest()
    )
    assert matching.status == "code"
    monkeypatch.setattr(target, name, original)
    assert await fixture.oauth.canonical_bearer(baseline["access_token"])
    assert isinstance(await fixture.oauth.exchange(params), dict)
    assert len(await rows(fixture, AuthorizedApplication)) == 2
    OBSERVATIONS.append(
        {
            "case": "exchange_rollback",
            "injection": failure_stage,
            "code_grant_credential_rollback": True,
            "same_code_exchange_after_recovery": True,
        }
    )


async def test_postgres_owner_and_workspace_bounds_survive_reconnect_and_revoke(pg_applications):
    from pyfly.security.context_holder import SecurityContextHolder

    from koinon.catalog.errors import AccessDenied

    fixture = pg_applications
    own_first = await connect(fixture)
    own_second = await connect(fixture, workspace=fixture.spaces[1].id)
    other_owner = await connect(fixture, subject=fixture.other)
    other_client = await connect(fixture, client="client-two")
    initial = await rows(fixture, AuthorizedApplication)
    first = next(
        row
        for row in initial
        if row.subject == fixture.subject
        and row.client_id == "client-one"
        and row.workspace_id == fixture.spaces[0].id
    )
    with pytest.raises(ResourceNotFoundException):
        await fixture.applications.revoke(fixture.other, first.id)
    with pytest.raises(ResourceNotFoundException):
        await fixture.applications.detail(fixture.other, first.id)
    updated = await connect(fixture)
    for preserved in (own_second, other_owner, other_client, updated):
        assert await fixture.oauth.canonical_bearer(preserved["access_token"])
    with pytest.raises(UnauthorizedException):
        await fixture.oauth.canonical_bearer(own_first["access_token"])
    security = await fixture.oauth.authenticate(updated["access_token"])
    marker = SecurityContextHolder.set_context(security)
    try:
        catalog = fixture.context.get_bean(CatalogService)
        await catalog.authorize(fixture.subject, fixture.tenant, "catalog:read", fixture.spaces[0].id)
        with pytest.raises(AccessDenied):
            await catalog.authorize(fixture.subject, fixture.tenant, "catalog:read", fixture.spaces[1].id)
    finally:
        SecurityContextHolder.reset_context(marker)
    applications = await rows(fixture, AuthorizedApplication)
    assert len(applications) == 5 and sum(row.revoked_at is None for row in applications) == 4
    OBSERVATIONS.append(
        {
            "case": "scope",
            "foreign_owner_management_denied": True,
            "other_workspace_and_client_preserved": True,
            "wrapper_cannot_widen_workspace": True,
        }
    )


async def test_postgres_last_used_updates_are_coarse_and_bound_to_the_same_connection(pg_applications):
    from sqlalchemy import update

    fixture = pg_applications
    created = await connect(fixture)
    assert (await rows(fixture, AuthorizedApplication))[0].last_used_at is None
    raw = await fixture.oauth.canonical_bearer(created["access_token"])
    first_application = (await rows(fixture, AuthorizedApplication))[0]
    first_credential = (await rows(fixture, PersonalToken))[0]
    assert first_application.last_used_at is not None and first_credential.last_used_at is not None
    assert await fixture.oauth.canonical_bearer(created["access_token"])
    assert (await rows(fixture, AuthorizedApplication))[0].last_used_at == first_application.last_used_at
    assert (await rows(fixture, PersonalToken))[0].last_used_at == first_credential.last_used_at
    aged = datetime.now(UTC) - timedelta(minutes=6)
    async with infrastructure_unit(fixture.datasource) as session:
        await session.execute(
            update(AuthorizedApplication)
            .where(AuthorizedApplication.id == first_application.id)
            .values(last_used_at=aged)
        )
        await session.execute(
            update(PersonalToken).where(PersonalToken.id == first_credential.id).values(last_used_at=aged)
        )
    assert await fixture.tokens.authenticate(raw, purpose="application", application_id=first_application.id)
    assert (await rows(fixture, AuthorizedApplication))[0].last_used_at > aged
    assert (await rows(fixture, PersonalToken))[0].last_used_at > aged
    OBSERVATIONS.append(
        {"case": "last_used", "same_connection_credential_binding": True, "five_minute_coalescing": True}
    )


async def test_postgres_nested_recent_auth_keeps_its_grant_lock_across_the_touch_boundary(
    pg_applications, monkeypatch
):
    import koinon.authorized_applications.repositories as applications_module
    import koinon.tokens.repositories as tokens_repository_module
    import koinon.tokens.service as tokens_module

    fixture = pg_applications
    created = await connect(fixture)
    raw = await fixture.oauth.canonical_bearer(created["access_token"])
    application = (await rows(fixture, AuthorizedApplication))[0]
    moment = datetime.now(UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment if tz else moment.replace(tzinfo=None)

    for module in (applications_module, tokens_repository_module, tokens_module):
        monkeypatch.setattr(module, "datetime", Clock)
    recent, advance = asyncio.Event(), asyncio.Event()
    pids = {}

    async def nested_authentication():
        nonlocal moment
        async with infrastructure_unit(fixture.datasource) as session:
            await session.execute(text("SET LOCAL lock_timeout='8s'"))
            pids["auth"] = await session.scalar(text("SELECT pg_backend_pid()"))
            await fixture.tokens.authenticate(raw, purpose="application", application_id=application.id)
            recent.set()
            await advance.wait()
            moment += timedelta(minutes=6)
            await fixture.tokens.authenticate(raw, purpose="application", application_id=application.id)

    authenticating = asyncio.create_task(nested_authentication())
    await asyncio.wait_for(recent.wait(), 5)
    revoking = asyncio.create_task(
        transaction(
            fixture, lambda: fixture.applications.revoke(fixture.subject, application.id), pids, "revoke"
        )
    )
    try:
        for _ in range(100):
            if "revoke" in pids:
                break
            await asyncio.sleep(0.01)
        assert pids["auth"] != pids["revoke"]
        await wait_blocked(fixture, pids["revoke"], pids["auth"])
    finally:
        advance.set()
    results = await asyncio.gather(authenticating, revoking, return_exceptions=True)
    assert not any(isinstance(value, BaseException) for value in results)
    assert (
        next(row for row in await rows(fixture, AuthorizedApplication) if row.id == application.id).revoked_at
        is not None
    )
    OBSERVATIONS.append(
        {
            "case": "nested_auth_boundary",
            "recent_auth_held_application_lock_through_outer_transaction": True,
            "controlled_clock_advanced_minutes": 6,
            "repeated_auth_did_not_deadlock": True,
        }
    )


async def test_postgres_authentication_last_used_updates_roll_back_together(pg_applications, monkeypatch):
    fixture = pg_applications
    created = await connect(fixture)
    original = fixture.tokens.applications.touch

    async def fail_application_touch(identifier):
        raise RuntimeError("Fictional activity update failure")

    monkeypatch.setattr(fixture.tokens.applications, "touch", fail_application_touch)
    with pytest.raises(RuntimeError, match="Fictional"):
        await fixture.oauth.canonical_bearer(created["access_token"])
    assert (await rows(fixture, AuthorizedApplication))[0].last_used_at is None
    assert (await rows(fixture, PersonalToken))[0].last_used_at is None
    monkeypatch.setattr(fixture.tokens.applications, "touch", original)
    assert await fixture.oauth.canonical_bearer(created["access_token"])
    OBSERVATIONS.append(
        {"case": "authentication_activity_rollback", "credential_and_application_activity_atomic": True}
    )


async def test_postgres_revoke_first_blocks_then_denies_stale_authentication(pg_applications, monkeypatch):
    fixture = pg_applications
    created = await connect(fixture)
    application = (await rows(fixture, AuthorizedApplication))[0]
    changed, release = asyncio.Event(), asyncio.Event()
    original = fixture.applications._revoke

    async def hold_revocation(row, action):
        await original(row, action)
        changed.set()
        await release.wait()

    monkeypatch.setattr(fixture.applications, "_revoke", hold_revocation)
    pids = {}
    revoking = asyncio.create_task(
        transaction(
            fixture, lambda: fixture.applications.revoke(fixture.subject, application.id), pids, "revoke"
        )
    )
    await asyncio.wait_for(changed.wait(), 5)
    authenticating = asyncio.create_task(
        transaction(
            fixture, lambda: fixture.oauth.canonical_bearer(created["access_token"]), pids, "authenticate"
        )
    )
    try:
        for _ in range(100):
            if "authenticate" in pids:
                break
            await asyncio.sleep(0.01)
        assert pids["authenticate"] != pids["revoke"]
        await wait_blocked(fixture, pids["authenticate"], pids["revoke"])
    finally:
        release.set()
    result = await asyncio.gather(revoking, authenticating, return_exceptions=True)
    assert result[0] is None and isinstance(result[1], UnauthorizedException)
    assert (await rows(fixture, AuthorizedApplication))[0].last_used_at is None
    assert (await rows(fixture, PersonalToken))[0].last_used_at is None
    OBSERVATIONS.append(
        {
            "case": "revoke_first",
            "authentication_waited_for_grant_lock": True,
            "revoked_connection_denied_after_lock_refresh": True,
        }
    )


async def test_postgres_one_code_cannot_commit_two_grants_on_independent_connections(pg_applications):
    from koinon.mcp_auth.service import OAuthError

    fixture = pg_applications
    params = await code(fixture)
    start = asyncio.Barrier(2)
    pids = {}

    async def exchange_once(label):
        async with infrastructure_unit(fixture.datasource) as session:
            pids[label] = await session.scalar(text("SELECT pg_backend_pid()"))
            await start.wait()
            return await fixture.oauth.exchange(params)

    result = await asyncio.gather(exchange_once("first"), exchange_once("second"), return_exceptions=True)
    assert pids["first"] != pids["second"]
    assert sum(isinstance(value, dict) for value in result) == 1
    denied = [value for value in result if isinstance(value, OAuthError)]
    assert len(denied) == 1 and denied[0].error == "invalid_grant"
    assert len(await rows(fixture, AuthorizedApplication)) == 1
    assert len(await rows(fixture, PersonalToken)) == 1
    OBSERVATIONS.append(
        {
            "case": "single_use_code",
            "independent_connections": True,
            "successful_code_exchanges": 1,
            "committed_grants_and_credentials": 1,
        }
    )
