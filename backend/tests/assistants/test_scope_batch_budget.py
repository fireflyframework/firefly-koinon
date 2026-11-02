# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.container.scanner import scan_package
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import event
from test_scope_read_budget import scoped_tree
from test_service import assistants as assistants

from koinon.authorized_applications.entities import AuthorizedApplication
from koinon.authorized_applications.repositories import AuthorizedApplicationRepository
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import TenantRepository
from koinon.mcp_applications.authority import McpOAuthClientAuthority
from koinon.mcp_applications.entities import McpOAuthClientRegistration
from koinon.mcp_applications.repositories import McpOAuthClientRepository
from koinon.mcp_auth.settings import McpOAuthSettings
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository


@pytest.mark.parametrize("assets", [1, 40])
@pytest.mark.parametrize("credential", ["session", "personal", "application", "registered"])
async def test_scope_reads_catalog_and_memberships_in_batches(assistants, assets, credential):
    service, context = assistants
    scope = await scoped_tree(service)
    first = await service.catalog.get("issuer|admin", "north", scope["asset_ids"][0])
    for index in range(assets - 1):
        row = await service.catalog.create(
            "issuer|admin", "north", kind="dataset", name=f"Dataset {index}", parent_id=first.parent_id
        )
        scope["asset_ids"].append(row.id)
    if credential != "session":
        context.register_bean(AuthorizedApplicationRepository)
        scan_package("koinon.tokens", context.container)
        service.catalog.restriction = context.get_bean(TokenRestriction)
        expires = datetime.now(UTC) + timedelta(hours=1)
        registration = None
        if credential == "registered":
            context.register_bean(McpOAuthClientRepository)
            registry = context.get_bean(McpOAuthClientRepository)
            await registry.save(
                McpOAuthClientRegistration(
                    id="registered-client",
                    tenant_id="north",
                    client_id="fixture",
                    name="Fixture",
                    client_type="public",
                    redirect_uris=["https://client.example.test/callback"],
                    scopes=["catalog:read", "chat:use"],
                    enabled=True,
                    revision=1,
                    created_by="issuer|admin",
                    updated_by="issuer|admin",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            authority = McpOAuthClientAuthority(
                registry, McpOAuthSettings(), context.get_bean(TenantRepository)
            )
            service.catalog.restriction.registrations = authority
            registration = authority.snapshot(await authority.resolve("fixture"))
        application = credential in {"application", "registered"}
        if application:
            await context.get_bean(AuthorizedApplicationRepository).save(
                AuthorizedApplication(
                    id="scope-application",
                    subject="issuer|viewer",
                    client_id="fixture",
                    name="Scoped application",
                    resource="https://knowledge.example.test/mcp",
                    tenant_id="north",
                    tenant_name="North",
                    workspace_id=scope["workspace_id"],
                    workspace_name="Workspace",
                    scopes=["catalog:read", "chat:use"],
                    connected_at=datetime.now(UTC),
                    expires_at=expires,
                    client_registration=registration,
                )
            )
        await context.get_bean(PersonalTokenRepository).save(
            PersonalToken(
                id="scope-reader",
                subject="issuer|viewer",
                tenant_id="north",
                name="Scoped reader",
                token_hash="0" * 64,
                prefix="fixture",
                scopes=["catalog:read", "chat:use"],
                workspace_ids=[scope["workspace_id"]],
                purpose="application" if application else "personal",
                authorized_application_id="scope-application" if application else None,
                expires_at=expires,
            )
        )
    engine = context.get_bean(DataSourceRegistry).primary.engine.sync_engine
    statements = []

    def capture(connection, cursor, statement, parameters, execution, many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with SecurityContextHolder.using(
            SecurityContext(
                user_id="viewer",
                attributes={
                    "iss": "issuer",
                    "sub": "viewer",
                    **({"koinon_token_id": "scope-reader"} if credential != "session" else {}),
                },
            )
        ):
            assert await service.validate_scope("issuer|viewer", "north", scope) == scope
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    budget = {"session": 3, "personal": 4, "application": 5, "registered": 6}[credential]
    assert len(statements) <= budget, f"Scope of {assets} assets issued {len(statements)} SQL statements"


async def test_batched_ancestry_does_not_admit_a_foreign_parent(assistants):
    service, _ = assistants
    scope = await scoped_tree(service)
    row = await service.catalog.catalog_repository.find_by_id(scope["asset_ids"][0])
    foreign = await service.catalog.create("issuer|outsider", "south", kind="workspace", name="Private")
    row.parent_id = foreign.id
    await service.catalog.catalog_repository.save(row)
    with pytest.raises(AccessDenied):
        await service.validate_scope("issuer|viewer", "north", scope)


async def test_batched_ancestry_does_not_admit_a_missing_entry(assistants):
    service, _ = assistants
    scope = await scoped_tree(service)
    scope["asset_ids"].append("absent-entry")
    with pytest.raises(AccessDenied):
        await service.validate_scope("issuer|viewer", "north", scope)


async def test_batched_ancestry_is_bounded_and_still_rejects_cycles(assistants):
    from pyfly.kernel import InvalidRequestException

    service, _ = assistants
    scope = await scoped_tree(service)
    root = await service.catalog.catalog_repository.find_by_id(scope["workspace_id"])
    root.parent_id = scope["asset_ids"][0]
    await service.catalog.catalog_repository.save(root)
    with pytest.raises(InvalidRequestException, match="ancestry"):
        await service.validate_scope("issuer|viewer", "north", scope)
