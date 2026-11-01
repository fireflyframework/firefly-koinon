# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.security.context import SecurityContext
from starlette.requests import Request

from koinon.bootstrap.dtos import BootstrapSeedInput
from koinon.bootstrap.repositories import BootstrapGrantRepository
from koinon.bootstrap.service import BootstrapGrants
from koinon.catalog.entities import AuditEvent
from koinon.catalog.repositories import AuditRepository, MembershipRepository, TenantRepository
from koinon.communications.ports import WelcomeAdmissionPort
from koinon.communications.repositories import NotificationRepository, OutboxRepository
from koinon.security.settings import OidcSettings

TID = "00000000-0000-4000-8000-000000000001"
OID = "00000000-0000-4000-8000-000000000002"
ISSUER = f"https://login.microsoftonline.com/{TID}/v2.0"
CLIENT = "inert-bootstrap-client"


def seed(**overrides):
    values = dict(
        issuer=ISSUER,
        client_id=CLIENT,
        entra_tenant_id=TID,
        grants=[dict(object_id=OID, role="admin", expires_at=datetime.now(UTC) + timedelta(days=1))],
    )
    values.update(overrides)
    return BootstrapSeedInput.model_validate(values)


def login(*, subject="pairwise-sub", oid=OID, tid=TID, audience=CLIENT, path="/login/oauth2/code/koinon"):
    request = Request({"type": "http", "path": path, "method": "GET", "headers": []})
    registration = SimpleNamespace(
        client_id=CLIENT, issuer_uri=ISSUER, redirect_uri="https://app.invalid/login/oauth2/code/koinon"
    )
    context = SecurityContext(
        user_id=subject,
        attributes={"iss": ISSUER, "sub": subject, "oid": oid, "tid": tid, "aud": audience, "azp": CLIENT},
    )
    return request, registration, context


@pytest.fixture
async def runtime(tmp_path):
    from pyfly.data.relational.sqlalchemy import Base
    from sqlalchemy import create_engine

    from koinon.bootstrap.entities import BootstrapIdentityGrant
    from koinon.catalog.entities import CatalogEntry, Membership, Tenant
    from koinon.communications.entities import (
        BootstrapContactRecord,
        InstallationRecord,
        NotificationRecord,
        OutboxRecord,
        WelcomeAdmissionRecord,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'bootstrap.db'}")
    tables = {
        Tenant.__table__,
        CatalogEntry.__table__,
        Membership.__table__,
        AuditEvent.__table__,
        BootstrapIdentityGrant.__table__,
        InstallationRecord.__table__,
        OutboxRecord.__table__,
        NotificationRecord.__table__,
        WelcomeAdmissionRecord.__table__,
        BootstrapContactRecord.__table__,
    }
    while dependencies := {key.column.table for table in tables for key in table.foreign_keys} - tables:
        tables.update(dependencies)
    Base.metadata.create_all(engine, tables=list(tables))
    engine.dispose()
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'bootstrap.db'}",
                        }
                    },
                }
            }
        )
    )
    oidc = OidcSettings(
        issuer=ISSUER,
        client_id=CLIENT,
        api_audience="inert-api",
        jwks_uri=ISSUER + "/certs",
        authorization_uri=ISSUER + "/authorize",
        token_uri=ISSUER + "/token",
        redirect_uri="https://app.invalid/login/oauth2/code/koinon",
    )
    context.container.register_instance(OidcSettings, oidc)
    for kind in (
        TenantRepository,
        MembershipRepository,
        AuditRepository,
        BootstrapGrantRepository,
        BootstrapGrants,
        NotificationRepository,
        OutboxRepository,
    ):
        context.register_bean(kind)

    class Welcome:
        fail = False

        async def admit(self, subject, tenant_id, *, bootstrap_grant_id=None):
            assert await context.get_bean(MembershipRepository).find_all(subject=subject, tenant_id=tenant_id)
            await context.get_bean(AuditRepository).save(
                AuditEvent(id=str(uuid4()), tenant_id=tenant_id, subject=subject, action="fixture.welcome")
            )
            if self.fail:
                raise RuntimeError("inert welcome failure")

    welcome = Welcome()
    context.container.register_instance(WelcomeAdmissionPort, welcome)
    await context.start()
    try:
        yield context, welcome
    finally:
        await context.stop()


async def test_operator_seeds_without_guessing_subject_then_verified_login_consumes_once(runtime):
    context, _ = runtime
    service = context.get_bean(BootstrapGrants)
    members = context.get_bean(MembershipRepository)
    await service.seed("inert-org", "Inert organization", seed())
    assert await members.find_all(tenant_id="inert-org") == []
    await service.observe_login(*login())
    rows = await members.find_all(tenant_id="inert-org")
    assert len(rows) == 1
    assert (
        rows[0].subject == ISSUER + "|pairwise-sub"
        and rows[0].role == "admin"
        and rows[0].workspace_id is None
    )
    grants = await context.get_bean(BootstrapGrantRepository).find_all(tenant_id="inert-org")
    assert grants[0].consumed_subject == rows[0].subject
    await service.observe_login(*login())
    assert len(await members.find_all(tenant_id="inert-org")) == 1
    assert len(await context.get_bean(AuditRepository).find_all(action="fixture.welcome")) == 1
    rows[0].active = False
    await members.save(rows[0])
    await service.observe_login(*login())
    assert not (await members.find_by_id(rows[0].id)).active
    assert len(await context.get_bean(AuditRepository).find_all(action="fixture.welcome")) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"oid": "00000000-0000-4000-8000-000000000099"},
        {"tid": "00000000-0000-4000-8000-000000000099"},
        {"audience": "inert-api"},
        {"path": "/api/v1/context"},
    ],
)
async def test_unmatched_identity_and_api_bearer_path_never_admit_admin(runtime, changes):
    context, _ = runtime
    service = context.get_bean(BootstrapGrants)
    await service.seed("inert-org", "Inert organization", seed())
    await service.observe_login(*login(**changes))
    assert await context.get_bean(MembershipRepository).find_all(tenant_id="inert-org") == []
    assert (await context.get_bean(BootstrapGrantRepository).find_all(tenant_id="inert-org"))[
        0
    ].consumed_at is None


async def test_welcome_failure_rolls_back_membership_audit_and_consumption(runtime):
    context, welcome = runtime
    service = context.get_bean(BootstrapGrants)
    await service.seed("inert-org", "Inert organization", seed())
    welcome.fail = True
    with pytest.raises(RuntimeError, match="inert welcome failure"):
        await service.observe_login(*login())
    assert await context.get_bean(MembershipRepository).find_all(tenant_id="inert-org") == []
    assert await context.get_bean(AuditRepository).find_all(action="fixture.welcome") == []
    assert (await context.get_bean(BootstrapGrantRepository).find_all(tenant_id="inert-org"))[
        0
    ].consumed_at is None


@pytest.mark.parametrize(
    "changes",
    [
        {"issuer": "https://wrong.invalid"},
        {"client_id": "wrong-client"},
        {"grants": [dict(object_id=OID, role="admin", expires_at=datetime.now(UTC) - timedelta(days=1))]},
    ],
)
async def test_operator_pins_and_expiry_are_checked_before_creating_org(runtime, changes):
    context, _ = runtime
    with pytest.raises(ValueError):
        await context.get_bean(BootstrapGrants).seed("inert-org", "Inert organization", seed(**changes))
    assert await context.get_bean(TenantRepository).find_by_id("inert-org") is None


async def test_concurrent_first_logins_create_one_membership_and_one_welcome(runtime):
    import asyncio

    context, _ = runtime
    service = context.get_bean(BootstrapGrants)
    await service.seed("inert-org", "Inert organization", seed())
    await asyncio.gather(service.observe_login(*login()), service.observe_login(*login()))
    assert len(await context.get_bean(MembershipRepository).find_all(tenant_id="inert-org")) == 1
    assert len(await context.get_bean(AuditRepository).find_all(action="fixture.welcome")) == 1


async def test_cancellation_rolls_back_activation_and_all_prior_effects(runtime):
    import asyncio

    context, welcome = runtime
    service = context.get_bean(BootstrapGrants)
    await service.seed("inert-org", "Inert organization", seed())
    original = welcome.admit

    async def cancelled(*args, **kwargs):
        await original(*args, **kwargs)
        raise asyncio.CancelledError

    welcome.admit = cancelled
    with pytest.raises(asyncio.CancelledError):
        await service.observe_login(*login())
    assert await context.get_bean(MembershipRepository).find_all(tenant_id="inert-org") == []
    assert await context.get_bean(AuditRepository).find_all(action="fixture.welcome") == []
    assert (await context.get_bean(BootstrapGrantRepository).find_all())[0].consumed_at is None


async def test_expired_pending_grant_never_activates(runtime, monkeypatch):
    context, _ = runtime
    service = context.get_bean(BootstrapGrants)
    await service.seed("inert-org", "Inert organization", seed())
    now = await context.get_bean(BootstrapGrantRepository).clock()

    async def later():
        return now + timedelta(days=2)

    monkeypatch.setattr(service.grants, "clock", later)
    await service.observe_login(*login())
    assert await context.get_bean(MembershipRepository).find_all(tenant_id="inert-org") == []


async def test_existing_inactive_membership_is_not_restored_by_pending_grant(runtime):
    from pyfly.kernel import ConflictException

    from koinon.catalog.entities import Membership

    context, _ = runtime
    service = context.get_bean(BootstrapGrants)
    await service.seed("inert-org", "Inert organization", seed())
    await context.get_bean(MembershipRepository).save(
        Membership(
            id="revoked", tenant_id="inert-org", subject=ISSUER + "|pairwise-sub", role="admin", active=False
        )
    )
    with pytest.raises(ConflictException):
        await service.observe_login(*login())
    assert not (await context.get_bean(MembershipRepository).find_by_id("revoked")).active
    assert (await context.get_bean(BootstrapGrantRepository).find_all())[0].consumed_at is None


async def test_actual_welcome_ledger_is_atomic_and_durable_after_new_service_and_brand_change(runtime):
    from koinon.communications.events import CommunicationEvents
    from koinon.communications.settings import CommunicationsSettings
    from koinon.communications.welcome import WelcomeAdmissions

    context, _ = runtime
    service = context.get_bean(BootstrapGrants)
    settings = CommunicationsSettings(enabled=True)
    events = CommunicationEvents(
        context.get_bean(OutboxRepository),
        context.get_bean(NotificationRepository),
        context.get_bean(TenantRepository),
        settings,
    )
    service.welcome = WelcomeAdmissions(context.get_bean(OutboxRepository), events)
    await service.seed("inert-org", "Inert organization", seed())
    await service.observe_login(*login())
    records = await context.get_bean(OutboxRepository).find_all(kind="welcome")
    assert len(records) == 1 and records[0].status == "suppressed"
    assert records[0].failure_code == "EMAIL_DISABLED"
    assert len(await context.get_bean(NotificationRepository).find_all(kind="welcome")) == 1
    member = (await context.get_bean(MembershipRepository).find_all(tenant_id="inert-org"))[0]
    await context.get_bean(MembershipRepository).delete_by_id(member.id)
    tenant = await context.get_bean(TenantRepository).find_by_id("inert-org")
    tenant.name = "Changed organization brand"
    await context.get_bean(TenantRepository).save(tenant)
    restarted = BootstrapGrants(
        service.grants, service.tenants, service.members, service.audits, service.oidc, service.welcome
    )
    await restarted.observe_login(*login())
    assert await context.get_bean(MembershipRepository).find_all(tenant_id="inert-org") == []
    assert len(await context.get_bean(OutboxRepository).find_all(kind="welcome")) == 1


@pytest.mark.parametrize("id_token_present", [True, False])
async def test_only_actual_strict_native_id_token_callback_runs_bootstrap_before_refresh(
    runtime, id_token_present
):
    import json
    import time
    from urllib.parse import urlencode

    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from pyfly.security.oauth2.client import ClientRegistration, InMemoryClientRegistrationRepository
    from pyfly.session.session import HttpSession

    from koinon.corporate_identity.login import CorporateLoginSuccess
    from koinon.security.oidc import IdentityTokenValidator, VerifiedOidcLoginHandler

    context, _ = runtime
    service = context.get_bean(BootstrapGrants)
    await service.seed("inert-org", "Inert organization", seed())
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public.update(kid="inert-key", use="sig", alg="RS256")
    registration = ClientRegistration(
        registration_id="koinon",
        client_id=CLIENT,
        issuer_uri=ISSUER,
        jwks_uri=ISSUER + "/certs",
        authorization_uri=ISSUER + "/authorize",
        token_uri=ISSUER + "/token",
        user_info_uri="https://userinfo.invalid",
        redirect_uri=service.oidc.redirect_uri,
        scopes=["openid"],
        require_iss=True,
    )
    refreshed = []

    class Refresh:
        async def login(self, verified):
            rows = await context.get_bean(MembershipRepository).find_all(tenant_id="inert-org")
            assert len(rows) == 1 and rows[0].subject == ISSUER + "|actual-signed-pairwise"
            refreshed.append(verified.user_id)

    class Profiles:
        async def get(self, *args):
            pass

    handler = VerifiedOidcLoginHandler(
        InMemoryClientRegistrationRepository(registration),
        validator_factory=lambda _: IdentityTokenValidator(
            ISSUER + "/certs",
            issuer=ISSUER,
            audiences=[CLIENT],
            jwks_fetcher=lambda *a, **kw: json.dumps({"keys": [public]}).encode(),
            leeway=0,
        ),
        authentication_success_handler=CorporateLoginSuccess(None, Refresh(), Profiles(), bootstrap=service),
    )
    from starlette.responses import JSONResponse

    from koinon.security.oidc import ApiBearerFilter

    api_token = jwt.encode(
        dict(
            iss=ISSUER,
            sub="actual-signed-pairwise",
            oid=OID,
            tid=TID,
            aud="inert-api",
            azp=CLIENT,
            exp=int(time.time()) + 300,
        ),
        key,
        algorithm="RS256",
        headers={"kid": "inert-key"},
    )
    bearer = ApiBearerFilter(
        IdentityTokenValidator(
            ISSUER + "/certs",
            issuer=ISSUER,
            audiences=["inert-api"],
            jwks_fetcher=lambda *a, **kw: json.dumps({"keys": [public]}).encode(),
            leeway=0,
        )
    )
    api_request = Request(
        {
            "type": "http",
            "path": "/api/v1/context",
            "method": "GET",
            "headers": [(b"authorization", ("Bearer " + api_token).encode())],
        }
    )

    async def after_bearer(value):
        assert value.state.security_context.attributes["oid"] == OID
        return JSONResponse({"verified": True})

    assert (await bearer.do_filter(api_request, after_bearer)).status_code == 200
    assert await context.get_bean(MembershipRepository).find_all(tenant_id="inert-org") == []
    assert refreshed == []
    session = HttpSession("before-login", is_new=True)

    def request(query=""):
        value = Request(
            {
                "type": "http",
                "path": "/login/oauth2/code/koinon",
                "method": "GET",
                "headers": [(b"x-oid", b"forged-object")],
                "query_string": query.encode(),
                "path_params": {"registration_id": "koinon"},
            }
        )
        value.state.session = session
        return value

    await handler.routes()[0].endpoint(request())

    async def exchange(*args):
        value = {"access_token": "inert-access"}
        if id_token_present:
            value["id_token"] = jwt.encode(
                dict(
                    iss=ISSUER,
                    sub="actual-signed-pairwise",
                    oid=OID,
                    tid=TID,
                    aud=CLIENT,
                    azp=CLIENT,
                    nonce=session.get_attribute("oauth2_nonce"),
                    exp=int(time.time()) + 300,
                ),
                key,
                algorithm="RS256",
                headers={"kid": "inert-key"},
            )
        return value

    async def userinfo(*args):
        pytest.fail("Userinfo must never supply bootstrap authority")

    handler._exchange_code, handler._fetch_user_info = exchange, userinfo
    query = urlencode(
        dict(state=session.get_attribute("oauth2_state"), code="inert-code", iss=ISSUER, oid="forged-object")
    )
    if id_token_present:
        response = await handler.routes()[1].endpoint(request(query))
        assert response.status_code == 302 and refreshed == ["actual-signed-pairwise"]
        assert session.get_attribute("SECURITY_CONTEXT").user_id != OID
    else:
        response = await handler.routes()[1].endpoint(request(query))
        assert response.status_code == 401
        assert json.loads(response.body)["error"] == "oidc_id_token_required"
        assert refreshed == []
        assert await context.get_bean(MembershipRepository).find_all(tenant_id="inert-org") == []
