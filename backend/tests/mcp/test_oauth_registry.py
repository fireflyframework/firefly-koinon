# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError


def test_empty_registry_can_start_without_authorizing_any_client():
    from koinon.mcp_auth.settings import McpOAuthSettings

    settings = McpOAuthSettings(enabled=True, encryption_key=Fernet.generate_key().decode())
    assert settings.clients == []


@pytest.mark.parametrize(
    "changes",
    [
        {"redirect_uris": ["https://client.example/callback#fragment"]},
        {"redirect_uris": ["http://remote.example/callback"]},
        {"redirect_uris": ["https://*.example/callback"]},
        {"scopes": ["catalog:read", "identity:manage"]},
        {"scopes": ["ingest:write"]},
        {"client_id": "chosen"},
        {"client_secret": "chosen"},
        {"tenant_id": "other"},
    ],
)
def test_registration_input_cannot_add_management_authority_or_ambiguous_callbacks(changes):
    from koinon.mcp_applications.dtos import McpOAuthClientInput

    with pytest.raises(ValidationError):
        McpOAuthClientInput(
            **{
                "name": "Research client",
                "client_type": "public",
                "redirect_uris": ["https://client.example/callback"],
                "scopes": ["catalog:read", "knowledge:search"],
                **changes,
            }
        )


@pytest.fixture
async def registry(tmp_path):
    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository
    from koinon.mcp.settings import McpSettings
    from koinon.mcp_applications.service import McpOAuthClientRegistry
    from koinon.mcp_auth.settings import McpOAuthSettings
    from koinon.tokens.authorization import TokenRestriction
    from koinon.tokens.repositories import PersonalTokenRepository

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'registry.db'}",
                        }
                    },
                }
            }
        )
    )
    for package in ("koinon.catalog", "koinon.mcp_applications"):
        scan_package(package, context.container)
    context.register_bean(TokenRestriction)
    context.register_bean(PersonalTokenRepository)
    context.register_bean(McpSettings)
    context.register_bean(McpOAuthSettings)
    await context.start()
    try:
        tenants = context.get_bean(TenantRepository)
        members = context.get_bean(MembershipRepository)
        for tenant in ("north", "south"):
            await tenants.save(Tenant(id=tenant, name=tenant))
            await members.save(
                Membership(id=tenant, subject="issuer|" + tenant, tenant_id=tenant, role="admin")
            )
        await members.save(Membership(id="viewer", subject="issuer|viewer", tenant_id="north", role="viewer"))
        yield context.get_bean(McpOAuthClientRegistry), context
    finally:
        await context.stop()


def values(client_type="confidential"):
    from koinon.mcp_applications.dtos import McpOAuthClientInput

    return McpOAuthClientInput(
        name="Research client",
        client_type=client_type,
        redirect_uris=["https://client.example/callback"],
        scopes=["catalog:read", "knowledge:search"],
    )


async def test_confidential_secret_is_returned_once_and_only_a_hash_is_persisted(registry):
    from koinon.mcp_applications.repositories import McpOAuthClientRepository

    service, context = registry
    issued = await service.create("issuer|north", "north", values())
    assert issued.client.tenant_id == "north" and issued.client.revision == 1
    assert issued.client_secret and len(issued.client_secret) >= 43
    row = await context.get_bean(McpOAuthClientRepository).find_by_id(issued.client.id)
    assert row.client_secret_hash == hashlib.sha256(issued.client_secret.encode()).hexdigest()
    detail = await service.get("issuer|north", "north", issued.client.id)
    page = await service.page("issuer|north", "north")
    assert issued.client_secret not in str(detail.model_dump()) + str(page)
    assert row.client_secret_hash not in str(detail.model_dump()) + str(page)
    assert "client_secret" not in detail.model_dump()


async def test_public_clients_have_no_secret_and_cannot_rotate(registry):
    from pyfly.kernel import InvalidRequestException

    service, _ = registry
    issued = await service.create("issuer|north", "north", values("public"))
    assert issued.client_secret is None
    with pytest.raises(InvalidRequestException):
        await service.rotate_secret("issuer|north", "north", issued.client.id, 1)


async def test_org_admin_cannot_manage_another_tenants_registration(registry):
    from koinon.catalog.errors import AccessDenied

    service, _ = registry
    issued = await service.create("issuer|north", "north", values())
    with pytest.raises(AccessDenied):
        await service.get("issuer|south", "north", issued.client.id)
    with pytest.raises(AccessDenied):
        await service.create("issuer|viewer", "north", values())
    assert (await service.page("issuer|south", "south"))["items"] == []


async def test_rotation_uses_current_revision_and_never_returns_previous_secret(registry):
    from pyfly.kernel import ConflictException

    service, _ = registry
    issued = await service.create("issuer|north", "north", values())
    rotated = await service.rotate_secret("issuer|north", "north", issued.client.id, 1)
    assert rotated.client.revision == 2 and rotated.client_secret != issued.client_secret
    with pytest.raises(ConflictException):
        await service.rotate_secret("issuer|north", "north", issued.client.id, 1)


async def test_runtime_snapshot_is_tenant_revision_and_configuration_bound(registry):
    from koinon.mcp_applications.authority import McpOAuthClientAuthority
    from koinon.mcp_applications.dtos import McpOAuthClientPatch

    service, context = registry
    authority = context.get_bean(McpOAuthClientAuthority)
    issued = await service.create("issuer|north", "north", values())
    resolved = await authority.resolve(issued.client.client_id)
    snapshot = authority.snapshot(resolved)
    assert snapshot["tenant_id"] == "north" and snapshot["revision"] == 1
    await authority.validate(issued.client.client_id, "north", snapshot)
    with pytest.raises(ValueError):
        await authority.validate(issued.client.client_id, "south", snapshot)
    await service.update(
        "issuer|north", "north", issued.client.id, McpOAuthClientPatch(expected_revision=1, enabled=False)
    )
    with pytest.raises(ValueError):
        await authority.validate(issued.client.client_id, "north", snapshot)


async def test_readiness_reports_an_invalid_disabled_key_without_returning_its_value(registry):
    service, _ = registry
    service.settings.encryption_key = "invalid"
    readiness = await service.readiness("issuer|north", "north")
    assert readiness.encryption_configured is False
    assert "oauth_encryption_key" in readiness.missing_configuration
    assert "invalid" not in readiness.model_dump_json()


async def test_registration_snapshot_rejects_boolean_revision_alias(registry):
    from koinon.mcp_applications.authority import McpOAuthClientAuthority

    service, context = registry
    authority = context.get_bean(McpOAuthClientAuthority)
    issued = await service.create("issuer|north", "north", values())
    snapshot = authority.snapshot(await authority.resolve(issued.client.client_id))
    with pytest.raises(ValueError):
        await authority.validate(issued.client.client_id, "north", {**snapshot, "revision": True})


async def test_registry_paging_filters_and_sorts_in_the_native_query(registry):
    from pyfly.kernel import InvalidRequestException

    service, _ = registry
    for name in ("Alpha", "Zulu"):
        await service.create("issuer|north", "north", values().model_copy(update={"name": name}))
    descending = await service.page("issuer|north", "north", sort="name", order="desc", page_size=1)
    assert descending["items"][0]["name"] == "Zulu"
    assert descending["total"] == 2 and descending["pages"] == 2
    recent = await service.page("issuer|north", "north", sort="updated_at", order="asc", q="Alpha")
    assert [row["name"] for row in recent["items"]] == ["Alpha"]
    with pytest.raises(InvalidRequestException):
        await service.page("issuer|north", "north", sort="client_secret_hash")


async def test_runtime_write_transaction_locks_tenant_before_registration(registry, monkeypatch):
    from pyfly.data import transactional
    from pyfly.data.relational.sqlalchemy import LockMode

    from koinon.catalog.repositories import TenantRepository
    from koinon.mcp_applications.authority import McpOAuthClientAuthority
    from koinon.mcp_applications.repositories import McpOAuthClientRepository

    service, context = registry
    issued = await service.create("issuer|north", "north", values())
    authority = context.get_bean(McpOAuthClientAuthority)
    calls = []
    tenant_read = TenantRepository.find_by_id
    registration_read = McpOAuthClientRepository.find_by_id

    async def tenant(self, identifier, **kwargs):
        calls.append(("tenant", identifier, kwargs.get("lock")))
        return await tenant_read(self, identifier, **kwargs)

    async def registration(self, identifier, **kwargs):
        calls.append(("registration", identifier, kwargs.get("lock")))
        return await registration_read(self, identifier, **kwargs)

    monkeypatch.setattr(TenantRepository, "find_by_id", tenant)
    monkeypatch.setattr(McpOAuthClientRepository, "find_by_id", registration)

    @transactional
    async def admitted_write():
        return await authority.resolve(issued.client.client_id)

    await admitted_write()
    assert calls == [
        ("tenant", "north", LockMode.PESSIMISTIC_READ),
        ("registration", issued.client.id, LockMode.PESSIMISTIC_READ),
    ]
    calls.clear()
    await authority.resolve(issued.client.client_id)
    assert calls == [("registration", issued.client.id, None)]
