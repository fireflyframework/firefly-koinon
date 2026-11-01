# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.availability.dtos import AvailabilityRequest
from koinon.knowledge.availability.service import KnowledgeAvailabilityService


@pytest.fixture(autouse=True)
def unit_without_native_registry(monkeypatch):
    @asynccontextmanager
    async def scope(**kwargs):
        yield None

    monkeypatch.setattr("koinon.knowledge.availability.service.primary_authority", scope)


def dependencies():
    row = SimpleNamespace(id="document", kind="document")
    facade = SimpleNamespace(_chain=AsyncMock(return_value=[row]))
    selection = {
        "id": "document",
        "kind": "document",
        "stamp": "stable",
        "domain": "canon",
        "native_id": "source",
        "native_workspace_id": "native",
        "phase": "unknown",
        "latest_attempt": None,
        "blocked": False,
    }
    records = SimpleNamespace(load=AsyncMock(return_value={"document": selection}))
    observation = {
        "stamp": "native-v1",
        "revision": {"source_version_id": "v1", "extraction_id": "e1"},
        "read": {"state": "ready", "reason": "CURRENT_TEXT_RECORDED"},
        "search": {"state": "pending", "reason": "ACTIVE_INDEX_INCOMPLETE"},
        "query": {"state": "not_applicable", "reason": "DOCUMENT"},
    }
    native = SimpleNamespace(observe=AsyncMock(return_value={"document": observation}))
    return KnowledgeAvailabilityService(facade, records, native), facade, records, native


async def test_native_current_text_can_complete_without_inventing_queue_and_search_is_separate(monkeypatch):
    service, _, _, _ = dependencies()
    result = await service.observe("reader", "tenant", AvailabilityRequest(asset_ids=["document"]))
    value = result.items["document"]
    assert value.phase == "complete"
    assert value.read.state == "ready" and value.search.state == "pending"
    assert value.revision.source_version_id == "v1"


async def test_authority_is_checked_before_native_access_and_again_before_release():
    service, facade, _, native = dependencies()
    facade._chain.side_effect = AccessDenied("Revoked")
    with pytest.raises(AccessDenied):
        await service.observe("revoked", "tenant", AvailabilityRequest(asset_ids=["document"]))
    native.observe.assert_not_awaited()
    facade._chain.side_effect = [[SimpleNamespace(id="document", kind="document")], AccessDenied("Revoked")]
    with pytest.raises(AccessDenied):
        await service.observe("reader", "tenant", AvailabilityRequest(asset_ids=["document"]))


async def test_native_or_primary_drift_downgrades_all_capabilities():
    for drift in ("native", "primary"):
        service, _, records, native = dependencies()
        if drift == "native":
            native.observe.side_effect = [native.observe.return_value, {}]
        else:
            records.load.side_effect = [records.load.return_value, {}]
        result = await service.observe("reader", "tenant", AvailabilityRequest(asset_ids=["document"]))
        assert result.items["document"].read.state == "unknown"
        assert result.items["document"].read.reason == "OBSERVATION_CHANGED"


async def test_failed_new_attempt_preserves_observed_old_serving_revision():
    service, _, records, _ = dependencies()
    records.load.return_value["document"]["latest_attempt"] = {
        "id": "attempt-v2",
        "state": "failed",
        "operation": "document.replace",
    }
    result = await service.observe("reader", "tenant", AvailabilityRequest(asset_ids=["document"]))
    value = result.items["document"]
    assert value.phase == "failed" and value.latest_attempt.id == "attempt-v2"
    assert value.read.state == "ready" and value.revision.source_version_id == "v1"


async def test_only_durable_queue_state_produces_queued_phase():
    service, _, records, native = dependencies()
    records.load.return_value["document"]["phase"] = "queued"
    native.observe.return_value = {}
    result = await service.observe("reader", "tenant", AvailabilityRequest(asset_ids=["document"]))
    assert result.items["document"].phase == "queued"
    assert result.items["document"].search.state == "unknown"


def test_request_is_bounded_unique_and_strict():
    for identifiers in ([], ["x"] * 2, [str(i) for i in range(101)], [""], [5]):
        with pytest.raises(ValidationError):
            AvailabilityRequest(asset_ids=identifiers)
