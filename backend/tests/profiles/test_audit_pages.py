# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, date, datetime

import pytest
from pyfly.kernel import InvalidRequestException
from test_profiles import profiles as profiles

from koinon.catalog.entities import AuditEvent
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import AuditRepository
from koinon.catalog.service import CatalogService


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
                action="evidence.reviewed",
                resource_id=workspace.id,
                created_at=datetime(2026, 3, 8, 12, index, tzinfo=UTC),
            )
        )
    result = await service.audit_page("issuer|admin", "north", q="Researcher", page=2, page_size=10)
    assert result["total"] == 23 and result["pages"] == 3 and len(result["items"]) == 10
    assert result["items"][0].id == "proof-012"
    assert (
        await service.audit_page("issuer|admin", "north", q="Audit evidence", action="evidence.reviewed")
    )["total"] == 23
    assert (await service.audit_page("issuer|admin", "north", q="%"))["total"] == 0
    assert (await service.audit_page("issuer|admin", "north", subject="issuer|member"))["total"] == 23
    with pytest.raises(AccessDenied):
        await service.audit_page("issuer|member", "north")
    with pytest.raises(AccessDenied):
        await service.audit_page("issuer|admin", "south")


async def test_audit_date_window_uses_selected_timezone_and_daylight_saving(profiles):
    _, context = profiles
    service = context.get_bean(CatalogService)
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
                action="time.boundary",
                created_at=datetime.fromisoformat(timestamp),
            )
        )
    result = await service.audit_page(
        "issuer|admin",
        "north",
        action="time.boundary",
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
