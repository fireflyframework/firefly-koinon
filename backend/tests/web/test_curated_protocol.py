# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from conftest import bearer


@pytest.fixture(autouse=True)
def register_curated(monkeypatch):
    from pyfly.container.scanner import scan_package

    import koinon.app
    from koinon.knowledge.curated.controllers import CuratedKnowledgeController
    from koinon.web.projection import register_controller

    original = koinon.app.create_application

    def composed(config):
        app = original(config)
        scan_package("koinon.knowledge.curated", app.state.context.container)
        register_controller(app.state.context, CuratedKnowledgeController)
        return app

    monkeypatch.setattr(koinon.app, "create_application", composed)


def test_native_signed_http_requires_exact_explicit_consent_and_preserves_pending_outcome(client):
    base = "/api/v1/tenants/north"
    parent = client.workspace_id
    for kind in ("project", "collection"):
        result = client.post(
            base + "/catalog", headers=bearer(), json={"kind": kind, "name": kind, "parent_id": parent}
        )
        assert result.status_code == 201, result.text
        parent = result.json()["id"]
    values = {
        "action": "create_published",
        "destination_id": parent,
        "content": {"title": "User-authorized fact", "body": "The threshold is47"},
        "origin": {"kind": "user_statement"},
    }
    assert client.post(base + "/knowledge-intents", headers=bearer("viewer"), json=values).status_code == 403
    response = client.post(base + "/knowledge-intents", headers=bearer(), json=values)
    assert response.status_code == 201, response.text
    assert "no-store" in response.headers["cache-control"]
    preview = response.json()
    url = base + "/knowledge-intents/" + preview["id"]
    assert client.get(url, headers=bearer("viewer")).status_code == 403
    assert client.get(base + "/knowledge-items", headers=bearer()).json()["total"] == 0
    confirmation = {
        "confirm": True,
        "expected_revision": preview["revision"],
        "authorization_digest": preview["authorization_digest"],
    }
    assert client.post(url + "/confirm", headers=bearer(), json=confirmation).status_code == 400
    assert (
        client.post(
            url + "/confirm",
            headers={**bearer(), "Idempotency-Key": "exact"},
            json={**confirmation, "confirm": "true"},
        ).status_code
        == 422
    )
    from koinon.knowledge.curated.intents import KnowledgeIntents
    from koinon.knowledge.curated.ports import NativeCommitUncertain

    class NativeBoundary:
        async def receipt(self, *args):
            return None

        async def commit(self, operation):
            raise NativeCommitUncertain()

    service = client.native_app.state.context.get_bean(KnowledgeIntents)
    service.native = SimpleNamespace(get=lambda: NativeBoundary())
    pending = client.post(
        url + "/confirm", headers={**bearer(), "Idempotency-Key": "exact"}, json=confirmation
    )
    assert pending.status_code == 202, pending.text
    assert pending.json() == {
        "status": "pending",
        "operation_id": preview["id"],
        "intent_id": preview["id"],
        "reason": "commit_outcome_unresolved",
    }
    assert client.get(base + "/knowledge-items", headers=bearer()).json()["items"] == []
