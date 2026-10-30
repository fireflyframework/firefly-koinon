# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The audit transport uses its injected service without request application state."""

import json
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from koinon.assistants.controllers import AssistantController
from koinon.catalog.errors import AccessDenied


@pytest.mark.parametrize("denied", [False, True])
async def test_audit_uses_injected_authority_service_without_application_lookup(monkeypatch, denied):
    calls = []

    class Audits:
        async def get(self, subject, tenant_id, run_id):
            calls.append((subject, tenant_id, run_id))
            if denied:
                raise AccessDenied("Unavailable", code="ACCESS_DENIED")
            return {"run_id": "saved-run", "provenance_status": "recorded"}

    monkeypatch.setattr(
        "koinon.assistants.controllers.identity_from_request",
        lambda request: SimpleNamespace(subject="issuer|owner"),
    )
    controller = AssistantController(object(), object(), Audits())
    request = Request({"type": "http", "method": "GET", "path": "/audit", "headers": []})
    if denied:
        with pytest.raises(AccessDenied):
            await controller.audit("tenant", "saved-run", request)
    else:
        response = await controller.audit("tenant", "saved-run", request)
        assert json.loads(response.body) == {"run_id": "saved-run", "provenance_status": "recorded"}
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
    assert calls == [("issuer|owner", "tenant", "saved-run")]
