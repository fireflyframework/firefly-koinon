# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owned PostgreSQL proof for batched, fresh primary policy observations."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from pyfly.core import PyFlyApplication
from pyfly.data.transaction import current_unit_of_work
from sqlalchemy import text
from sqlalchemy.engine import make_url
from test_policy_runtime_scope import snapshot
from test_search_batch_budget import (
    test_document_admission_and_model_checks_use_bounded_sql_batches as assert_batched_reads,
)
from test_search_batch_budget import (
    test_model_batch_rechecks_authority_after_native_await as assert_model_revocation,
)

from koinon.app import KoinonApplication
from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.knowledge.repositories import DomainBindingRepository
from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings

pytestmark = pytest.mark.integration


@pytest.fixture
async def postgres_context(tmp_path, record_property):
    uri = os.environ.get("KOINON_MEMORY_AUTHORITY_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    url = make_url(uri)
    assert url.host == "127.0.0.1" and url.port != 18783
    database = "search_admission_" + uuid4().hex[:12]
    with psycopg.connect(uri, autocommit=True) as owner:
        owner.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    record_property("owned_database", database)
    native_url = url.set(drivername="postgresql+asyncpg", database=database).render_as_string(
        hide_password=False
    )
    config = tmp_path / "pyfly.yaml"
    config.write_text(
        "pyfly:\n  banner:\n    mode: off\n  data:\n    relational:\n      enabled: true\n"
        f"      ddl-auto: create\n      url: {native_url!r}\n"
    )
    app = PyFlyApplication(KoinonApplication, config_path=str(config))
    app.context.register_bean(DomainBindingRepository)
    await app.startup()
    try:
        tenants = app.context.get_bean(TenantRepository)
        members = app.context.get_bean(MembershipRepository)
        for tenant in ("north", "south"):
            await tenants.save(Tenant(id=tenant, name=tenant))
        for subject, tenant, role in (
            ("admin", "north", "admin"),
            ("reader", "north", "viewer"),
            ("outsider", "south", "admin"),
        ):
            await members.save(
                Membership(id=subject, subject=f"issuer|{subject}", tenant_id=tenant, role=role)
            )
        catalog = app.context.get_bean(CatalogService)
        parent, tree = None, {}
        for kind in ("workspace", "project", "collection"):
            entry = await catalog.create("issuer|admin", "north", kind=kind, name=kind, parent_id=parent)
            tree[kind], parent = entry, entry.id
        domains = SimpleNamespace(search=AsyncMock(return_value={"hits": []}))
        policies = SimpleNamespace(snapshot=AsyncMock(side_effect=lambda subject, tenant: snapshot(tenant)))
        facade = KnowledgeFacade(
            catalog,
            app.context.get_bean(DomainBindingRepository),
            domains,
            KnowledgeSettings(),
            knowledge_settings=policies,
        )
        yield facade, catalog, domains, tree, app.context
    finally:
        await app.shutdown()
    # Retain the uniquely named database for independent inspection.


@pytest.mark.parametrize("token", [False, True])
async def test_postgres_document_batches_keep_sql_growth_bounded(postgres_context, token, record_property):
    await assert_batched_reads(postgres_context, 201, token, record_property)


@pytest.mark.parametrize("change", ["membership", "token", "ancestor", "foreign_parent"])
async def test_postgres_model_rechecks_use_distinct_serializable_snapshots(
    postgres_context, change, monkeypatch, record_property
):
    facade, catalog, _, _, _ = postgres_context
    original = facade._read_chain
    units, isolation = [], []

    async def checked(subject, tenant, identifier, permission="catalog:read"):
        unit = current_unit_of_work("primary")
        assert unit is not None and unit.read_only and unit.read_from_primary
        if unit not in units:
            units.append(unit)
            isolation.append(
                await catalog.catalog_repository._require_session().scalar(text("SHOW transaction_isolation"))
            )
        return await original(subject, tenant, identifier, permission)

    monkeypatch.setattr(facade, "_read_chain", checked)
    await assert_model_revocation(postgres_context, change)
    assert len(units) == 3
    assert isolation == ["serializable"] * 3
    assert all(unit.completed for unit in units)
    assert current_unit_of_work("primary") is None
    record_property("primary_snapshot_isolation", ",".join(isolation))
