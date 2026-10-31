# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Authorization reads must distinguish a lagging replica from current primary policy."""

import hashlib
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pyfly.context.application_context import ApplicationContext
from pyfly.core.config import Config
from pyfly.data.relational.auto_configuration import RelationalAutoConfiguration
from pyfly.data.relational.sqlalchemy.entity import Base
from pyfly.data.transaction import Propagation, TransactionTemplate, current_unit_of_work
from pyfly.kernel import UnauthorizedException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine

from koinon.authorized_applications.entities import AuthorizedApplication
from koinon.catalog.entities import AuditEvent, CatalogEntry, Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import (
    AuditRepository,
    CatalogRepository,
    MembershipRepository,
    TenantRepository,
)
from koinon.catalog.service import CatalogService
from koinon.corporate_identity.access import CorporateMembershipReader
from koinon.corporate_identity.entities import CorporateGrant, CorporateMapping, CorporateProvider
from koinon.corporate_identity.refresh import CorporateAccessRefresh
from koinon.corporate_identity.repositories import (
    CorporateGrantRepository,
    CorporateMappingRepository,
    CorporateProviderRepository,
)
from koinon.security.settings import OidcSettings
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository
from koinon.tokens.service import PersonalTokenService
from koinon.tokens.settings import TokenSettings

ISSUER = "https://authority-fixture.invalid"
SUBJECT = ISSUER + "|principal"
TOKEN_ID = "a" * 32
TOKEN = "koinon_pat_" + TOKEN_ID + "." + "b" * 43
NOW = datetime.now(UTC)


class NoProvider:
    def __getattr__(self, name):
        raise AssertionError("Provider use is forbidden: " + name)


@pytest.fixture
async def authority(tmp_path):
    urls = {name: "sqlite+aiosqlite:///" + str(tmp_path / (name + ".db")) for name in ("primary", "replica")}
    tables = [
        Tenant.__table__,
        CatalogEntry.__table__,
        Membership.__table__,
        AuditEvent.__table__,
        AuthorizedApplication.__table__,
        PersonalToken.__table__,
        CorporateProvider.__table__,
        CorporateMapping.__table__,
        CorporateGrant.__table__,
    ]
    for name, url in urls.items():
        stale = name == "replica"
        engine = create_async_engine(url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all, tables=tables)
                await connection.execute(Tenant.__table__.insert(), {"id": "tenant", "name": "Inert fixture"})
                await connection.execute(
                    Membership.__table__.insert(),
                    {
                        "id": "local",
                        "subject": SUBJECT,
                        "tenant_id": "tenant",
                        "role": "admin",
                        "active": stale,
                    },
                )
                await connection.execute(
                    PersonalToken.__table__.insert(),
                    {
                        "id": TOKEN_ID,
                        "purpose": "personal",
                        "subject": SUBJECT,
                        "tenant_id": "tenant",
                        "name": "Inert credential",
                        "token_hash": hashlib.sha256(TOKEN.encode()).hexdigest(),
                        "prefix": "fixture",
                        "scopes": ["catalog:read", "members:write", "audit:read"],
                        "expires_at": NOW + timedelta(hours=1),
                        "revoked_at": None if stale else NOW,
                        "last_used_at": NOW,
                    },
                )
                await connection.execute(
                    CorporateProvider.__table__.insert(),
                    {
                        "id": "provider",
                        "tenant_id": "tenant",
                        "kind": "keycloak",
                        "name": "Stored fixture only",
                        "canonical_issuer": ISSUER,
                        "source_key": "fixture",
                        "status": "active" if stale else "disabled",
                        "created_by": SUBJECT,
                        "updated_by": SUBJECT,
                    },
                )
                await connection.execute(
                    CorporateMapping.__table__.insert(),
                    {
                        "id": "mapping",
                        "tenant_id": "tenant",
                        "provider_id": "provider",
                        "group_id": "group",
                        "group_name": "Fixture group",
                        "role": "admin",
                        "enabled": stale,
                        "revision": 1,
                    },
                )
                await connection.execute(
                    CorporateGrant.__table__.insert(),
                    {
                        "id": "managed",
                        "tenant_id": "tenant",
                        "provider_id": "provider",
                        "mapping_id": "mapping",
                        "subject": SUBJECT,
                        "external_subject": "external",
                        "role": "admin",
                        "policy_revision": 1,
                        "mapping_revision": 1,
                        "active": stale,
                        "observed_at": NOW,
                        "expires_at": NOW + timedelta(hours=1),
                    },
                )
        finally:
            await engine.dispose()
    config = Config(
        {
            "pyfly": {
                "data": {
                    "relational": {
                        "enabled": "true",
                        "url": urls["primary"],
                        "ddl-auto": "none",
                        "read-replica": {"url": urls["replica"]},
                    }
                }
            }
        }
    )
    ctx = ApplicationContext(config)
    repos = (
        TenantRepository,
        MembershipRepository,
        CatalogRepository,
        AuditRepository,
        PersonalTokenRepository,
        CorporateProviderRepository,
        CorporateMappingRepository,
        CorporateGrantRepository,
    )
    for bean in (RelationalAutoConfiguration, *repos):
        ctx.register_bean(bean)
    await ctx.start()
    try:
        get = ctx.get_bean
        oidc = OidcSettings(
            issuer=ISSUER,
            jwks_uri=ISSUER + "/jwks",
            client_id="fixture",
            api_audience="fixture",
            authorization_uri=ISSUER + "/authorize",
            token_uri=ISSUER + "/token",
            redirect_uri=ISSUER + "/callback",
        )
        refresh = CorporateAccessRefresh(
            get(CorporateProviderRepository),
            get(CorporateMappingRepository),
            get(CorporateGrantRepository),
            NoProvider(),
            NoProvider(),
            get(AuditRepository),
            oidc,
        )
        reader = CorporateMembershipReader(get(CorporateGrantRepository), oidc, refresh)
        managed_catalog = CatalogService(
            get(TenantRepository),
            get(MembershipRepository),
            get(CatalogRepository),
            get(AuditRepository),
            managed_memberships=reader,
        )
        local_catalog = CatalogService(
            get(TenantRepository), get(MembershipRepository), get(CatalogRepository), get(AuditRepository)
        )
        restriction = TokenRestriction(get(PersonalTokenRepository), get(CatalogRepository))
        tokens = PersonalTokenService(
            get(PersonalTokenRepository), local_catalog, TokenSettings(), NoProvider()
        )
        yield SimpleNamespace(
            ctx=ctx, managed=managed_catalog, catalog=local_catalog, restriction=restriction, tokens=tokens
        )
    finally:
        await ctx.stop()


def caller_unit(caller):
    return (
        TransactionTemplate("primary", read_only=True).transaction() if caller == "replica" else nullcontext()
    )


@pytest.mark.parametrize("caller", ["outside", "replica"])
async def test_disabled_ciam_policy_cannot_authorize_from_replica(authority, caller):
    async with caller_unit(caller):
        with pytest.raises(AccessDenied):
            await authority.managed.authorize(SUBJECT, "tenant", "identity:manage")


@pytest.mark.parametrize("caller", ["outside", "replica"])
async def test_revoked_membership_cannot_authorize_from_replica(authority, caller):
    async with caller_unit(caller):
        with pytest.raises(AccessDenied):
            await authority.catalog.authorize(SUBJECT, "tenant", "members:write")


@pytest.mark.parametrize("caller", ["outside", "replica"])
async def test_revoked_pat_recheck_cannot_use_replica(authority, caller):
    context = SecurityContext(
        user_id="principal", attributes={"iss": ISSUER, "sub": "principal", "koinon_token_id": TOKEN_ID}
    )
    with SecurityContextHolder.using(context):
        async with caller_unit(caller):
            with pytest.raises(AccessDenied):
                await authority.restriction.grant(SUBJECT)


async def test_pat_authentication_under_replica_unit_still_rejects_revocation(authority):
    async with TransactionTemplate("primary", read_only=True).transaction():
        with pytest.raises(UnauthorizedException):
            await authority.tokens.authenticate(TOKEN)


async def test_primary_writer_keeps_its_uncommitted_membership_and_credential(authority):
    token_id = "c" * 32
    token = "koinon_pat_" + token_id + "." + "d" * 43
    async with TransactionTemplate("primary").transaction() as writer:
        await writer.resource.execute(update(Membership).where(Membership.id == "local").values(active=True))
        await authority.ctx.get_bean(PersonalTokenRepository).save(
            PersonalToken(
                id=token_id,
                subject=SUBJECT,
                tenant_id="tenant",
                name="Uncommitted credential",
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                prefix="fixture",
                scopes=["catalog:read"],
                expires_at=NOW + timedelta(hours=1),
                last_used_at=NOW,
            )
        )
        await authority.catalog.authorize(SUBJECT, "tenant", "members:write")
        authenticated = await authority.tokens.authenticate(token)
        assert authenticated.attributes["koinon_token_id"] == token_id
        assert current_unit_of_work("primary") is writer


async def test_authority_entry_does_not_reuse_an_old_primary_read_snapshot(authority):
    async with TransactionTemplate("primary").transaction() as writer:
        await writer.resource.execute(update(Membership).where(Membership.id == "local").values(active=True))
    async with TransactionTemplate("primary", read_only=True, read_from_primary=True).transaction() as old:
        assert await old.resource.scalar(select(Membership.active).where(Membership.id == "local")) is True
        async with TransactionTemplate(
            "primary", propagation=Propagation.REQUIRES_NEW
        ).transaction() as writer:
            await writer.resource.execute(
                update(Membership).where(Membership.id == "local").values(active=False)
            )
        with pytest.raises(AccessDenied):
            await authority.catalog.authorize(SUBJECT, "tenant", "members:write")
        assert current_unit_of_work("primary") is old


async def test_nested_authority_participants_share_one_serializable_primary_unit(authority):
    from pyfly.data import Isolation

    from koinon.security.authority import primary_authority

    @primary_authority()
    async def participant():
        return current_unit_of_work("primary")

    @primary_authority()
    async def entry():
        unit = current_unit_of_work("primary")
        assert unit.read_only and unit.read_from_primary and unit.isolation is Isolation.SERIALIZABLE
        assert await participant() is unit
        return unit

    async with TransactionTemplate("primary", read_only=True).transaction() as replica:
        policy = await entry()
        assert policy is not replica
        assert current_unit_of_work("primary") is replica


@pytest.mark.parametrize("caller", ["outside", "replica"])
async def test_caller_context_does_not_publish_revoked_ciam_memberships(authority, caller):
    async with caller_unit(caller):
        context = await authority.managed.context(SUBJECT)
        assert context["memberships"] == []
        assert context["tenants"] == []
        assert context["workspace_permissions"] == {}


async def test_nested_pat_filter_denial_is_401_without_releasing_a_payload(authority):
    from starlette.requests import Request

    from koinon.security.oidc import ApiBearerFilter

    gate = ApiBearerFilter(NoProvider(), tokens=authority.tokens)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/context",
            "headers": [(b"authorization", ("Bearer " + TOKEN).encode())],
        }
    )

    async def release(_request):
        raise AssertionError("A revoked credential must not reach the protected handler")

    async with TransactionTemplate("primary", read_only=True).transaction():
        response = await gate.do_filter(request, release)
        assert response.status_code == 401


async def test_fresh_output_checks_get_a_new_primary_policy_snapshot(authority):
    from koinon.security.authority import primary_authority

    @primary_authority(fresh=True)
    async def fresh():
        return current_unit_of_work("primary")

    @primary_authority()
    async def entry():
        unit = current_unit_of_work("primary")
        verified = await fresh()
        assert verified is not unit and verified.read_from_primary and verified.read_only
        assert current_unit_of_work("primary") is unit

    await entry()


async def test_fixed_memory_policy_keeps_catalog_and_ciam_in_the_same_session(authority, monkeypatch):
    from koinon.assistants.memory.service import PersonalConversationMemory
    from koinon.security.authority import primary_authority

    async with TransactionTemplate("primary").transaction() as writer:
        await writer.resource.execute(update(Membership).values(active=True))
        await writer.resource.execute(update(CorporateProvider).values(status="active"))
        await writer.resource.execute(update(CorporateMapping).values(enabled=True))
        await writer.resource.execute(update(CorporateGrant).values(active=True))

    fixed, participants = [], []
    members = authority.ctx.get_bean(MembershipRepository)
    grants = authority.ctx.get_bean(CorporateGrantRepository)
    member_rows, managed_rows = members.find_all, grants.current

    async def observe_members(*args, **kwargs):
        participants.append(("membership", current_unit_of_work("primary"), members._session))
        return await member_rows(*args, **kwargs)

    async def observe_managed(*args, **kwargs):
        participants.append(("ciam", current_unit_of_work("primary"), grants._session))
        return await managed_rows(*args, **kwargs)

    monkeypatch.setattr(members, "find_all", observe_members)
    monkeypatch.setattr(grants, "current", observe_managed)

    class Observation:
        async def observe_bound(self, *args, **kwargs):
            assert current_unit_of_work("primary") is fixed[0]
            return "observed in the fixed policy unit"

    memory = PersonalConversationMemory(
        NoProvider(),
        Observation(),
        NoProvider(),
        authority.managed,
        SimpleNamespace(max_history_messages=40, max_history_tokens=8192),
        NoProvider(),
    )

    @primary_authority(fresh=True)
    async def fresh_participant():
        unit = current_unit_of_work("primary")
        participants.append(("fresh-participant", unit, unit.resource))

    async def validate():
        fixed.append(current_unit_of_work("primary"))
        await authority.managed.authorize(SUBJECT, "tenant", "identity:manage")
        await authority.managed.memberships(SUBJECT)
        await fresh_participant()

    async with TransactionTemplate("primary", read_only=True).transaction() as replica:
        await memory.authorize_fixed(SUBJECT, "tenant", (), (), validate=validate)
        assert fixed[0] is not replica
        assert current_unit_of_work("primary") is replica
    assert {name for name, _, _ in participants} == {"membership", "ciam", "fresh-participant"}
    assert all(unit is fixed[0] and session is fixed[0].resource for _, unit, session in participants)


async def test_writing_authentication_unit_keeps_native_default_isolation(authority):
    from pyfly.data import Isolation

    from koinon.security.authority import primary_authority

    @primary_authority(read_only=False)
    async def authenticate():
        unit = current_unit_of_work("primary")
        assert unit.read_from_primary and not unit.read_only
        assert unit.isolation is Isolation.DEFAULT

    await authenticate()
