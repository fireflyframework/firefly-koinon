# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.container.scanner import scan_package
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import current_unit_of_work
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import event
from test_facade import context as context

from koinon.catalog.entities import CatalogEntry
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.entities import DomainBinding
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository


async def documents(context, count):
    facade, catalog, _, tree, _ = context
    source = await catalog.create(
        "issuer|admin", "north", kind="source", name="Originals", parent_id=tree["collection"].id
    )
    await facade._bind(
        "issuer|admin", "north", tree["workspace"], "canon", "native-workspace", "native-workspace"
    )
    rows = []
    for index in range(count):
        row = CatalogEntry(
            id=f"document-{index}",
            tenant_id="north",
            kind="document",
            name=f"Document {index}",
            parent_id=source.id,
            workspace_id=tree["workspace"].id,
            project_id=tree["project"].id,
            status="ready",
            created_by="issuer|admin",
            updated_by="issuer|admin",
        )
        await catalog.catalog_repository.save(row)
        await facade.bindings.save(
            DomainBinding(
                id=f"binding-{index}",
                tenant_id="north",
                catalog_id=row.id,
                workspace_id=row.workspace_id,
                domain="canon",
                entity_kind="document",
                native_id=f"native-{index}",
                native_workspace_id="native-workspace",
                created_by="issuer|admin",
            )
        )
        rows.append(row)
    return rows


async def scoped_token(context):
    _, catalog, _, tree, app = context
    scan_package("koinon.tokens", app.container)
    catalog.restriction = app.get_bean(TokenRestriction)
    token = PersonalToken(
        id="reader-token",
        subject="issuer|reader",
        tenant_id="north",
        name="Read originals",
        token_hash="0" * 64,
        prefix="fixture",
        scopes=["catalog:read", "knowledge:search"],
        workspace_ids=[tree["workspace"].id],
        asset_ids=[tree["collection"].id],
        resource_ids=[tree["workspace"].id, tree["project"].id],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await app.get_bean(PersonalTokenRepository).save(token)
    return token


def security(token=False):
    return SecurityContextHolder.using(
        SecurityContext(
            user_id="reader",
            attributes={
                "iss": "issuer",
                "sub": "reader",
                **({"koinon_token_id": "reader-token"} if token else {}),
            },
        )
    )


@pytest.mark.parametrize("count", [1, 40, 201, 1001])
@pytest.mark.parametrize("token", [False, True])
async def test_document_admission_and_model_checks_use_bounded_sql_batches(
    context, count, token, record_property
):
    facade, _, domains, _, app = context
    rows = await documents(context, count)
    if token:
        await scoped_token(context)
    engine = app.get_bean(DataSourceRegistry).primary.engine.sync_engine
    statements, counts = [], []

    def observe(connection, cursor, statement, parameters, execution, many):
        statements.append(statement)

    async def native_search(**values):
        assert current_unit_of_work("primary") is None
        assert set(values["source_ids"]) == {f"native-{index}" for index in range(count)}
        assert set(values["_capture"].canonical_documents.values()) == {row.id for row in rows}
        counts.append(len(statements))
        for _ in range(2):
            statements.clear()
            await values["_capture"].authorize()
            assert current_unit_of_work("primary") is None
            counts.append(len(statements))
        return {"hits": []}

    domains.search.side_effect = native_search
    event.listen(engine, "before_cursor_execute", observe)
    try:
        with security(token):
            await facade.search("issuer|reader", "north", question="evidence")
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    batches = (count + 199) // 200
    for phase, observed in zip(("admission", "model_first", "model_fresh"), counts, strict=True):
        record_property(f"{phase}_sql", observed)
    assert counts[0] <= 8 + 2 * batches, f"Admission of {count} documents issued {counts[0]} statements"
    assert max(counts[1:]) <= 3 + batches, f"Fresh model checks issued {counts[1:]} statements"


@pytest.mark.parametrize("change", ["membership", "token", "ancestor", "foreign_parent"])
async def test_model_batch_rechecks_authority_after_native_await(context, change):
    facade, catalog, domains, tree, app = context
    rows = await documents(context, 3)
    token = await scoped_token(context) if change == "token" else None

    async def native_search(**values):
        assert current_unit_of_work("primary") is None
        await values["_capture"].authorize()
        if change == "membership":
            await catalog.membership_repository.delete_by_id("reader")
        elif change == "token":
            token.revoked_at = datetime.now(UTC)
            await app.get_bean(PersonalTokenRepository).save(token)
        else:
            row = await catalog.catalog_repository.find_by_id(tree["collection"].id)
            if change == "ancestor":
                row.status = "archived"
            else:
                foreign = await catalog.create("issuer|outsider", "south", kind="workspace", name="Foreign")
                row.parent_id = foreign.id
            await catalog.catalog_repository.save(row)
        await values["_capture"].authorize()
        pytest.fail("A revoked source reached model execution")

    domains.search.side_effect = native_search
    with security(token is not None), pytest.raises(AccessDenied):
        await facade.search("issuer|reader", "north", question="evidence", asset_ids=[row.id for row in rows])


@pytest.mark.parametrize(
    "change",
    [
        "missing_binding",
        "foreign_binding",
        "workspace_binding",
        "missing_entry",
        "foreign_parent",
        "archived",
    ],
)
async def test_batch_admission_preserves_invalid_source_denials(context, change):
    facade, catalog, domains, tree, _ = context
    rows = await documents(context, 3)
    if change == "missing_entry":
        with pytest.raises(AccessDenied):
            await facade.search(
                "issuer|reader", "north", question="evidence", asset_ids=[rows[0].id, "missing"]
            )
        domains.search.assert_not_awaited()
        return
    if change == "missing_binding":
        await facade.bindings.delete_by_id("binding-1")
    elif change in {"foreign_binding", "workspace_binding"}:
        binding = await facade.bindings.find_by_id("binding-1")
        if change == "foreign_binding":
            binding.tenant_id = "south"
        else:
            binding.native_workspace_id = "foreign-native"
        await facade.bindings.save(binding)
    else:
        row = await catalog.catalog_repository.find_by_id(tree["collection"].id)
        if change == "archived":
            row.status = "archived"
        else:
            foreign = await catalog.create("issuer|outsider", "south", kind="workspace", name="Foreign")
            row.parent_id = foreign.id
        await catalog.catalog_repository.save(row)
    with pytest.raises(AccessDenied):
        await facade.search("issuer|reader", "north", question="evidence", asset_ids=[row.id for row in rows])
    domains.search.assert_not_awaited()


async def test_binding_observations_expire_before_the_next_search(context):
    facade, _, domains, _, _ = context
    rows = await documents(context, 3)
    await facade.search("issuer|reader", "north", question="evidence")
    binding = await facade.bindings.find_by_id("binding-1")
    binding.native_workspace_id = "changed-after-admission"
    await facade.bindings.save(binding)
    domains.search.reset_mock()
    with pytest.raises(AccessDenied):
        await facade.search("issuer|reader", "north", question="evidence", asset_ids=[row.id for row in rows])
    domains.search.assert_not_awaited()


async def test_asset_root_does_not_implicitly_grant_ancestor_access(context):
    facade, _, domains, _, app = context
    rows = await documents(context, 3)
    token = await scoped_token(context)
    token.resource_ids = []
    await app.get_bean(PersonalTokenRepository).save(token)
    with security(True), pytest.raises(AccessDenied):
        await facade.search("issuer|reader", "north", question="evidence", asset_ids=[rows[0].id])
    domains.search.assert_not_awaited()
