# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import test_profiles as profile_fixture
from pyfly.kernel import InvalidRequestException

from koinon.catalog.entities import AuditEvent
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import AuditRepository
from koinon.catalog.service import CatalogService

spec = importlib.util.spec_from_file_location(
    "audit_pg_fixture",
    Path(__file__).resolve().parents[1] / "integrations/content_sources/test_source_migration_postgres.py",
)
assert spec and spec.loader
postgres = importlib.util.module_from_spec(spec)
spec.loader.exec_module(postgres)
source_database = postgres.source_database


@pytest.fixture
async def profiles(source_database, tmp_path, monkeypatch):
    target, _, engine = source_database
    postgres.upgrade_sources(engine)
    original = profile_fixture.Config

    def configuration(values):
        values["pyfly"]["data"]["relational"].update(
            {
                "url": target.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False),
                "ddl-auto": "none",
            }
        )
        return original(values)

    monkeypatch.setattr(profile_fixture, "Config", configuration)
    async for value in profile_fixture.profiles.__wrapped__(tmp_path):
        yield value


async def test_audit_filters_count_and_page_before_returning_rows(profiles):
    profile, context = profiles
    service = context.get_bean(CatalogService)
    await profile.update("issuer|member", {"display_name": "Named Researcher"})
    workspace = await service.create("issuer|admin", "north", kind="workspace", name="Audit evidence")
    for index in range(23):
        await context.get_bean(AuditRepository).save(
            AuditEvent(
                id=f"proof-{index:03}",
                tenant_id="north",
                subject="issuer|member",
                action="catalog.updated",
                resource_id=workspace.id,
                created_at=datetime(2026, 3, 8, 12, index, tzinfo=UTC),
            )
        )
    result = await service.audit_page("issuer|admin", "north", q="Researcher", page=2, page_size=10)
    assert result["total"] == 23 and result["pages"] == 3 and len(result["items"]) == 10
    assert result["items"][0].id == "proof-012"
    assert (await service.audit_page("issuer|admin", "north", q="Audit evidence", action="catalog.updated"))[
        "total"
    ] == 23
    assert (await service.audit_page("issuer|admin", "north", q="%"))["total"] == 0
    assert (await service.audit_page("issuer|admin", "north", subject="issuer|member"))["total"] == 23
    with pytest.raises(AccessDenied):
        await service.audit_page("issuer|member", "north")
    with pytest.raises(AccessDenied):
        await service.audit_page("issuer|admin", "south")


async def test_audit_date_window_uses_selected_timezone_and_daylight_saving(profiles):
    _, context = profiles
    service = context.get_bean(CatalogService)
    workspace = await service.create("issuer|admin", "north", kind="workspace", name="Audit calendar")
    for index, timestamp in enumerate(
        (
            "2026-03-08T07:30:00+00:00",
            "2026-03-08T08:30:00+00:00",
            "2026-03-09T06:30:00+00:00",
            "2026-03-09T07:30:00+00:00",
        )
    ):
        await context.get_bean(AuditRepository).save(
            AuditEvent(
                id=f"time-{index}",
                tenant_id="north",
                subject="issuer|admin",
                action="catalog.updated",
                resource_id=workspace.id,
                created_at=datetime.fromisoformat(timestamp),
            )
        )
    result = await service.audit_page(
        "issuer|admin",
        "north",
        action="catalog.updated",
        from_date=date(2026, 3, 8),
        through_date=date(2026, 3, 8),
        time_zone="America/Los_Angeles",
    )
    assert {row.id for row in result["items"]} == {"time-1", "time-2"}
    for values in (
        {"time_zone": "Invented/Zone"},
        {"page": 0},
        {"page_size": 101},
        {"sort": "subject"},
        {"from_date": date(2026, 3, 9), "through_date": date(2026, 3, 8)},
    ):
        with pytest.raises(InvalidRequestException):
            await service.audit_page("issuer|admin", "north", **values)
