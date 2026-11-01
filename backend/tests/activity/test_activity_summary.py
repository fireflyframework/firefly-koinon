# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config

from koinon.activity.dtos import ActivityWindow
from koinon.activity.ports import ActivitySummaryReader
from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService


@pytest.fixture
async def summary(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'summary.db'}",
                            "read-replica": {"url": f"sqlite+aiosqlite:///{tmp_path / 'empty-replica.db'}"},
                        }
                    },
                }
            }
        )
    )
    for package in ("koinon.catalog", "koinon.activity"):
        scan_package(package, context.container)
    await context.start()
    try:
        await context.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        await context.get_bean(MembershipRepository).save(
            Membership(id="admin", tenant_id="north", subject="issuer|admin", role="admin")
        )
        catalog = context.get_bean(CatalogService)
        parent, project, workspace = None, None, None
        for kind in ("workspace", "project", "collection", "source", "document"):
            parent = await catalog.create(
                "issuer|admin", "north", kind=kind, name=kind.title(), parent_id=parent.id if parent else None
            )
            if kind == "workspace":
                workspace = parent
            if kind == "project":
                project = parent
        yield context, catalog, context.get_bean(ActivitySummaryReader), parent, project, workspace
    finally:
        await context.stop()


async def test_real_primary_history_is_personal_and_reports_unknown_telemetry_without_invented_zeros(summary):
    context, catalog, reader, document, project, _ = summary
    now = datetime.now(UTC)
    window = ActivityWindow(
        start_at=now - timedelta(hours=1), end_at=now + timedelta(seconds=1), time_zone="Europe/Madrid"
    )
    own = await reader.personal("issuer|admin", "north", window)
    assert own.knowledge.created.value == 1
    assert own.knowledge.consulted.status == "partial"
    assert len(own.top_projects) == 1 and own.top_projects[0].project_id == project.id
    assert own.mcp.requests.value is None and own.mcp.requests.status == "unavailable"
    assert own.models.input_tokens.value is None and own.models.cost.amount is None
    assert own.coverage.missing_observations is None and not own.coverage.complete_window
    await context.get_bean(MembershipRepository).save(
        Membership(id="viewer", tenant_id="north", subject="issuer|viewer", role="viewer")
    )
    other = await reader.personal("issuer|viewer", "north", window)
    assert other.knowledge.created.value == 0 and not other.top_projects
    admin = await reader.administrative("issuer|admin", "north", window)
    assert admin.knowledge.created.value == 1
    await catalog.archive("issuer|admin", "north", project.id)
    archived = await reader.personal("issuer|admin", "north", window)
    assert archived.knowledge.created.value == 0 and not archived.top_projects


async def test_summary_release_fails_if_authority_changes_after_aggregation(summary, monkeypatch):
    from koinon.activity.authority import ActivityAccess
    from koinon.catalog.errors import AccessDenied

    context, _, reader, _, _, _ = summary
    access = context.get_bean(ActivityAccess)
    original = access.resolve
    calls = 0

    async def changing(subject, tenant_id, *, administrative):
        nonlocal calls
        calls += 1
        value = await original(subject, tenant_id, administrative=administrative)
        if calls > 1:
            from dataclasses import replace

            return replace(value, fingerprint="current authority changed")
        return value

    monkeypatch.setattr(access, "resolve", changing)
    now = datetime.now(UTC)
    with pytest.raises(AccessDenied, match="Activity access changed"):
        await reader.personal(
            "issuer|admin",
            "north",
            ActivityWindow(start_at=now - timedelta(hours=1), end_at=now, time_zone="UTC"),
        )


async def test_actual_revocation_between_primary_snapshots_prevents_summary_release(summary, monkeypatch):
    from contextlib import asynccontextmanager

    from koinon.catalog.errors import AccessDenied

    context, _, reader, _, _, _ = summary
    original = reader._snapshot
    completed = 0

    @asynccontextmanager
    async def interleaved():
        nonlocal completed
        async with original():
            yield
        completed += 1
        if completed == 1:
            await context.get_bean(MembershipRepository).delete_by_id("admin")

    monkeypatch.setattr(reader, "_snapshot", interleaved)
    now = datetime.now(UTC)
    with pytest.raises(AccessDenied):
        await reader.personal(
            "issuer|admin",
            "north",
            ActivityWindow(start_at=now - timedelta(hours=1), end_at=now, time_zone="UTC"),
        )


async def test_summary_does_not_select_private_or_unbounded_catalog_metadata(summary):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import event

    context, _, reader, _, _, _ = summary
    statements = []
    engine = context.get_bean(DataSourceRegistry).get("primary").engine

    def capture(connection, cursor, statement, parameters, execution_context, many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        now = datetime.now(UTC)
        await reader.personal(
            "issuer|admin",
            "north",
            ActivityWindow(start_at=now - timedelta(hours=1), end_at=now, time_zone="UTC"),
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    assert statements
    assert not any("lattice_catalog.metadata_json" in statement for statement in statements)
