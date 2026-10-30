# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from conftest import bearer


@pytest.fixture(autouse=True)
def register_external_reviews(monkeypatch):
    from pyfly.container.scanner import scan_package

    import koinon.app
    from koinon.knowledge.curated.controllers import CuratedKnowledgeController
    from koinon.knowledge.external_reviews.controllers import ExternalKnowledgeReviewController
    from koinon.web.projection import register_controller

    original = koinon.app.create_application

    def composed(config):
        app = original(config)
        for package in ("koinon.knowledge.curated", "koinon.knowledge.external_reviews"):
            scan_package(package, app.state.context.container)
        for controller in (CuratedKnowledgeController, ExternalKnowledgeReviewController):
            register_controller(app.state.context, controller)
        return app

    monkeypatch.setattr(koinon.app, "create_application", composed)


def setup(client):
    root = "/api/v1/tenants/north"
    parent = client.workspace_id
    for kind in ("project", "collection"):
        response = client.post(
            root + "/catalog", headers=bearer(), json={"kind": kind, "name": kind, "parent_id": parent}
        )
        assert response.status_code == 201, response.text
        parent = response.json()["id"]
    response = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "External application proof",
            "tenant_id": "north",
            "scopes": ["catalog:read", "catalog:write", "ingest:write"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "workspace_ids": [client.workspace_id],
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["token"]
    headers = {"Authorization": "Bearer " + token, "Idempotency-Key": "external-stage"}
    values = {
        "action": "create_draft",
        "destination_id": parent,
        "content": {"title": "Externally proposed", "body": "Requires explicit review."},
    }
    return root, headers, values


def test_signed_canonical_http_never_exposes_challenge_or_commits_generic_staging(client):
    root, headers, values = setup(client)
    response = client.post(root + "/external-knowledge-reviews", headers=headers, json=values)
    assert response.status_code == 201, response.text
    assert "no-store" in response.headers["cache-control"]
    review = response.json()
    assert review["review"]["evidence"][0]["authority"] == "unverified"
    assert "nonce" not in response.text
    url = root + "/external-knowledge-reviews/" + review["id"]
    assert client.get(url, headers=headers).json() == review
    assert client.post(url + "/challenge", headers=headers).status_code in {404, 405}
    decision = {
        "expected_revision": 1,
        "authorization_digest": review["review"]["authorization_digest"],
        "nonce": "x" * 43,
    }
    assert client.post(url + "/approve", headers=headers, json=decision).status_code == 403
    assert client.post(url + "/cancel", headers=headers, json=decision).status_code == 403
    bypass = {
        "confirm": True,
        "expected_revision": 1,
        "authorization_digest": review["review"]["authorization_digest"],
    }
    assert (
        client.post(
            root + "/knowledge-intents/" + review["id"] + "/confirm", headers=headers, json=bypass
        ).status_code
        == 403
    )
    assert client.get(root + "/knowledge-items", headers=headers).json()["total"] == 0
    assert client.post(root + "/external-knowledge-reviews", headers=bearer(), json=values).status_code == 400
    assert (
        client.post(
            root + "/external-knowledge-reviews", headers={**bearer(), "Idempotency-Key": "jwt"}, json=values
        ).status_code
        == 403
    )
