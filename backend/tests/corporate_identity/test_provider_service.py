# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.kernel import ConflictException

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.corporate_identity.dtos import IdentityProviderInput, IdentityProviderPatch
from koinon.corporate_identity.service import CorporateIdentityService
from koinon.security.settings import OidcSettings


@pytest.fixture
async def identities(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "agentic": {"enabled": True},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'identity.db'}",
                        }
                    },
                }
            }
        )
    )
    issuer = "https://identity.example.test/realms/koinon"
    context.container.register_instance(
        OidcSettings,
        OidcSettings(
            issuer=issuer,
            jwks_uri=issuer + "/certs",
            client_id="ui",
            api_audience="api",
            authorization_uri=issuer + "/auth",
            token_uri=issuer + "/token",
            redirect_uri="http://127.0.0.1:18781/login/oauth2/code/koinon",
            cookie_secure=False,
        ),
    )
    for package in ("koinon.catalog", "koinon.profiles", "koinon.corporate_identity"):
        scan_package(package, context.container)
    await context.start()
    try:
        await context.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        for subject, role in (("issuer|admin", "admin"), ("issuer|viewer", "viewer")):
            await context.get_bean(MembershipRepository).save(
                Membership(id=subject, subject=subject, tenant_id="north", role=role)
            )
        yield context.get_bean(CorporateIdentityService), context
    finally:
        await context.stop()


def local_input(name="Native corporate directory"):
    return IdentityProviderInput(
        kind="keycloak",
        name=name,
        settings={
            "kind": "keycloak",
            "issuer": "https://identity.example.test/realms/koinon",
            "client_id": "ui",
        },
    )


async def test_config_is_tenant_owned_revisioned_and_never_marks_discovery_active(identities):
    service, _ = identities
    created = await service.create("issuer|admin", "north", local_input())
    assert (
        created.status == "draft"
        and created.revision == 1
        and created.canonical_issuer == "https://identity.example.test/realms/koinon"
    )
    assert created.credential_configured is False and "credential" not in created.model_dump()
    updated = await service.update(
        "issuer|admin",
        "north",
        created.id,
        IdentityProviderPatch(expected_revision=1, name="Named directory"),
    )
    assert updated.revision == 2 and updated.name == "Named directory" and updated.status != "active"
    with pytest.raises(ConflictException):
        await service.update(
            "issuer|admin",
            "north",
            created.id,
            IdentityProviderPatch(expected_revision=1, name="Stale write"),
        )
    with pytest.raises(AccessDenied):
        await service.get("issuer|viewer", "north", created.id)
    with pytest.raises(AccessDenied):
        await service.get("issuer|admin", "south", created.id)
    page = await service.page("issuer|admin", "north", q="Named", page=1, page_size=1)
    assert page["total"] == 1 and page["pages"] == 1 and page["items"][0]["name"] == "Named directory"


async def test_missing_key_and_audit_failure_roll_back_without_touching_manual_grants(
    identities, monkeypatch
):
    from pyfly.kernel import ServiceUnavailableException

    from koinon.catalog.service import CatalogService

    service, context = identities
    body = IdentityProviderInput(
        **{**local_input().model_dump(), "credential": {"kind": "keycloak", "secret": "synthetic-only"}}
    )
    with pytest.raises(ServiceUnavailableException):
        await service.create("issuer|admin", "north", body)
    assert (await service.page("issuer|admin", "north"))["total"] == 0

    async def fail_audit(*args, **kwargs):
        raise RuntimeError("Controlled rollback")

    monkeypatch.setattr(context.get_bean(CatalogService), "_audit", fail_audit)
    with pytest.raises(RuntimeError):
        await service.create("issuer|admin", "north", local_input())
    assert (await service.page("issuer|admin", "north"))["total"] == 0
    assert len(await context.get_bean(MembershipRepository).find_all(tenant_id="north", active=True)) == 2


async def test_credential_omission_preserves_and_explicit_null_clears_native_ciphertext(identities):
    import base64

    from koinon.corporate_identity.repositories import CorporateProviderRepository
    from koinon.corporate_identity.settings import IdentitySettings

    service, context = identities
    context.get_bean(IdentitySettings).master_key = base64.b64encode(bytes(range(32))).decode()
    body = IdentityProviderInput(
        **{**local_input().model_dump(), "credential": {"kind": "keycloak", "secret": "synthetic-only"}}
    )
    created = await service.create("issuer|admin", "north", body)
    assert created.credential_configured is True
    encrypted = (await context.get_bean(CorporateProviderRepository).find_by_id(created.id)).secret_ciphertext
    renamed = await service.update(
        "issuer|admin", "north", created.id, IdentityProviderPatch(expected_revision=1, name="Renamed")
    )
    assert renamed.credential_configured is True and renamed.policy_revision == 1
    assert (
        await context.get_bean(CorporateProviderRepository).find_by_id(created.id)
    ).secret_ciphertext == encrypted
    cleared = await service.update(
        "issuer|admin", "north", created.id, IdentityProviderPatch(expected_revision=2, credential=None)
    )
    assert cleared.credential_configured is False and cleared.policy_revision == 2
    assert (
        await context.get_bean(CorporateProviderRepository).find_by_id(created.id)
    ).secret_ciphertext is None
