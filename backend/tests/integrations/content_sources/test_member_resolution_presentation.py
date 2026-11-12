# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reviewed synchronization choices survive reload without retained source names."""

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from pyfly.kernel import PyFlyException
from pyfly.security.context import SecurityContext
from pyfly.session.session import HttpSession
from pyfly.web.adapters.starlette.app import create_app
from pyfly.web.adapters.starlette.errors import global_exception_handler
from starlette.middleware.base import BaseHTTPMiddleware
from test_connection_lifecycle import lifecycle as lifecycle
from test_mapping_policy_service import empty_listing as empty_listing
from test_mapping_review import review as review
from test_source_migration_postgres import source_database as source_database

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_policies import SourcePolicies
from koinon.integrations.content_sources.sync_dtos import SourcePolicyReviewInput

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("schedule", [{"kind": "manual"}, {"kind": "interval", "seconds": 3600}])
async def test_review_page_restores_normalized_policy_and_next_occurrence(empty_listing, schedule):
    value = empty_listing
    policies = value.context.get_bean(SourcePolicies)
    request = SourcePolicyReviewInput(
        **{**value.request.model_dump(), "formats": [".txt", ".pdf"], "schedule": schedule},
        operation_id=str(uuid4()),
    )
    receipt = await policies.review("issuer|alice", "tenant", "browser-a", request)
    before = datetime.now(UTC)
    page = await policies.items("issuer|alice", "tenant", receipt.policy_id, browser_session="browser-a")
    after = datetime.now(UTC)
    data = page.model_dump(mode="json")
    assert data["normalized_policy"]["formats"] == [".pdf", ".txt"]
    assert data["normalized_policy"]["schedule"] == schedule
    assert data["normalized_policy"]["destination"] == request.destination.model_dump(mode="json")
    if schedule["kind"] == "manual":
        assert data["next_occurrence_at"] is None
    else:
        actual = datetime.fromisoformat(data["next_occurrence_at"].replace("Z", "+00:00"))
        assert before + timedelta(hours=1) <= actual <= after + timedelta(hours=1)


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_excluded_names_are_fresh_and_removed_after_permission_loss(empty_listing, monkeypatch):
    value = empty_listing
    value.state.parents["other"] = ("selected",)
    value.state.parents["z-other"] = ("selected",)
    original = value.service.browser._source
    state = {"name": "Current excluded folder", "denied": False}

    @asynccontextmanager
    async def source(scope, tokens):
        async with original(scope, tokens) as adapter:
            original_get = adapter.get_item

            async def get_item(identifier):
                if identifier == "other" and state["denied"]:
                    raise SourceError("access_denied")
                item = await original_get(identifier)
                return replace(item, name=state["name"]) if identifier == "other" else item

            adapter.get_item = get_item
            yield adapter

    monkeypatch.setattr(value.service.browser, "_source", source)
    policies = value.context.get_bean(SourcePolicies)
    receipt = await policies.review(
        "issuer|alice", "tenant", "browser-a",
        SourcePolicyReviewInput(
            **{**value.request.model_dump(), "excluded_ids": ["other", "z-other"]},
            operation_id=str(uuid4()),
        ),
    )
    app = create_app(context=value.context, actuator_enabled=False)
    app.add_exception_handler(PyFlyException, global_exception_handler)

    async def identity(request, next_handler):
        request.state.security_context = SecurityContext(
            user_id="alice", attributes={"iss": "issuer", "sub": "alice"}
        )
        request.state.session = HttpSession("browser-a")
        return await next_handler(request)

    app.add_middleware(BaseHTTPMiddleware, dispatch=identity)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/tenants/tenant/content-sources/mappings/{receipt.mapping_id}/excluded-items",
            params={"limit": 1},
        )
        assert response.status_code == 200, response.text
        assert [item["item_id"] for item in response.json()["items"]] == ["other"]
    current = await policies.excluded_items(
        "issuer|alice", "tenant", "browser-a", mapping_id=receipt.mapping_id, limit=1
    )
    assert current.model_dump()["items"] == [{
        "item_id": "other", "name": "Current excluded folder", "kind": "folder",
        "relative_path": ["Current excluded folder"],
    }]
    assert current.next_cursor is not None
    calls = len(value.state.calls)
    with pytest.raises(SourceError):
        await policies.excluded_items(
            "issuer|alice", "tenant", "browser-b", mapping_id=receipt.mapping_id,
            limit=1, cursor=current.next_cursor,
        )
    assert len(value.state.calls) == calls
    state["name"] = "Renamed excluded folder"
    page = await policies.excluded_items(
        "issuer|alice", "tenant", "browser-a", review_id=receipt.policy_id, limit=1
    )
    assert page.items[0].name == state["name"]
    state["denied"] = True
    current = await policies.excluded_items(
        "issuer|alice", "tenant", "browser-a", mapping_id=receipt.mapping_id, limit=1
    )
    assert current.items == [] and current.next_cursor is not None
    assert "Renamed excluded folder" not in current.model_dump_json()
    last = await policies.excluded_items(
        "issuer|alice", "tenant", "browser-a", mapping_id=receipt.mapping_id,
        limit=1, cursor=current.next_cursor,
    )
    assert [item.item_id for item in last.items] == ["z-other"] and last.next_cursor is None
