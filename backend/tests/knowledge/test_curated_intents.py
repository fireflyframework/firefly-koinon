# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private review is not repository publication or authority to change its content."""

from hashlib import sha256

import pytest


@pytest.fixture
async def curated(tmp_path):
    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository
    from koinon.catalog.service import CatalogService
    from koinon.knowledge.curated.intents import KnowledgeIntents
    from koinon.knowledge.repositories import DomainBindingRepository
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
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'curated.db'}",
                        }
                    },
                }
            }
        )
    )
    for package in ("koinon.catalog", "koinon.knowledge.curated"):
        scan_package(package, context.container)
    context.register_bean(PersonalTokenRepository)
    context.register_bean(TokenRestriction)
    context.register_bean(DomainBindingRepository)
    await context.start()
    try:
        for tenant in ("north", "south"):
            await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant))
        for subject, tenant, role in (
            ("owner", "north", "editor"),
            ("reader", "north", "viewer"),
            ("foreign", "south", "admin"),
        ):
            await context.get_bean(MembershipRepository).save(
                Membership(id=subject, subject="issuer|" + subject, tenant_id=tenant, role=role)
            )
        catalog = context.get_bean(CatalogService)
        parent = None
        for kind in ("workspace", "project", "collection"):
            parent = await catalog.create(
                "issuer|owner", "north", kind=kind, name=kind, parent_id=parent.id if parent else None
            )
        yield context.get_bean(KnowledgeIntents), catalog, parent, context
    finally:
        await context.stop()


def input_for(destination, **changes):
    return {
        "action": "create_draft",
        "destination_id": destination.id,
        "content": {"title": "Reviewed operating rule", "body": "The renewal threshold is 47."},
        "origin": {"kind": "user_statement"},
        **changes,
    }


async def committed_projection(context, preview, receipt):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import select

    from koinon.knowledge.curated.ports import NativeCatalogProjection
    from koinon.knowledge.entities import DomainBinding

    async with infrastructure_unit(context.get_bean(DataSourceRegistry).get("primary")) as session:
        alias = await session.scalar(
            select(DomainBinding).where(DomainBinding.catalog_id == preview.destination.workspace_id)
        )
        if alias is None:
            session.add(
                DomainBinding(
                    id="native-workspace-alias",
                    tenant_id=preview.tenant_id,
                    catalog_id=preview.destination.workspace_id,
                    workspace_id=preview.destination.workspace_id,
                    domain="canon",
                    entity_kind="workspace",
                    native_id="native-space",
                    native_workspace_id="native-space",
                    created_by=preview.owner_subject,
                )
            )
    return NativeCatalogProjection(
        native_workspace_id="native-space",
        title=preview.after.title,
        summary=preview.after.summary,
        serving_version_id=receipt.native_version_id if receipt.serving_version else None,
        serving_operation_id=receipt.operation_id if receipt.serving_version else None,
    )


async def test_private_preview_records_exact_user_authorship_without_native_commit(curated):
    service, _, destination, context = curated
    from koinon.knowledge.curated.repositories import KnowledgeIntentRepository

    preview = await service.preview("issuer|owner", "north", input_for(destination))
    assert preview.status == "preview" and preview.revision == 1
    assert preview.action == "create_draft" and preview.receipt is None
    statement = preview.evidence[0]
    assert statement.kind == "user_statement" and statement.author_subject == "issuer|owner"
    assert statement.text == "The renewal threshold is 47."
    assert statement.sha256 == sha256(statement.text.encode()).hexdigest()
    assert preview.authorization_digest and statement.recorded_at
    assert len(await context.get_bean(KnowledgeIntentRepository).find_all()) == 1
    from koinon.knowledge.curated.ports import NativeKnowledgeCommitPort

    assert not context.container.contains_type(NativeKnowledgeCommitPort)
    assert await service.get("issuer|owner", "north", preview.id) == preview


async def test_private_preview_requires_both_write_permissions_and_owner_reads(curated):
    from koinon.catalog.errors import AccessDenied

    service, _, destination, _ = curated
    for subject, tenant in (("issuer|reader", "north"), ("issuer|foreign", "north")):
        with pytest.raises(AccessDenied):
            await service.preview(subject, tenant, input_for(destination))
    preview = await service.preview("issuer|owner", "north", input_for(destination))
    with pytest.raises(AccessDenied):
        await service.get("issuer|reader", "north", preview.id)


async def test_action_and_exact_confirmation_cannot_be_defaulted_or_coerced(curated):
    from pydantic import ValidationError

    from koinon.knowledge.curated.dtos import KnowledgeConfirmation, KnowledgeIntentInput

    _, _, destination, _ = curated
    values = input_for(destination)
    del values["action"]
    with pytest.raises(ValidationError):
        KnowledgeIntentInput.model_validate(values)
    for confirm in (None, False, 1, "true"):
        with pytest.raises(ValidationError):
            KnowledgeConfirmation(confirm=confirm, expected_revision=1, authorization_digest="a" * 64)


async def test_native_port_refuses_a_preview_without_durable_explicit_confirmation(curated):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.curated.ports import NativeKnowledgeOperation

    service, _, destination, context = curated
    preview = await service.preview("issuer|owner", "north", input_for(destination))
    native = service.native.get()
    assert native is not None
    with pytest.raises(AccessDenied) as failure:
        await native.commit(NativeKnowledgeOperation(preview, ()))
    assert failure.value.code == "KNOWLEDGE_CONFIRMATION_REQUIRED"
    assert context.get_bean(DataSourceRegistry).names() == ["primary"]


@pytest.mark.parametrize("scopes", [["catalog:read", "catalog:write"], ["catalog:read", "ingest:write"]])
async def test_actual_token_permission_intersection_requires_both_mutation_scopes(curated, scopes):
    from datetime import UTC, datetime, timedelta

    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder

    from koinon.catalog.errors import AccessDenied
    from koinon.tokens.entities import PersonalToken
    from koinon.tokens.repositories import PersonalTokenRepository

    service, _, destination, context = curated
    token = PersonalToken(
        id="limited",
        subject="issuer|owner",
        tenant_id="north",
        name="Limited",
        token_hash="a" * 64,
        prefix="limited",
        scopes=scopes,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await context.get_bean(PersonalTokenRepository).save(token)
    with (
        SecurityContextHolder.using(
            SecurityContext(
                user_id="owner", attributes={"iss": "issuer", "sub": "owner", "koinon_token_id": token.id}
            )
        ),
        pytest.raises(AccessDenied),
    ):
        await service.preview("issuer|owner", "north", input_for(destination))
