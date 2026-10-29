# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from conftest import ISSUER, bearer
from flycanon.config import CanonSettings
from flyquery.config import FlyquerySettings

from koinon.catalog.entities import Membership
from koinon.catalog.repositories import MembershipRepository
from koinon.catalog.service import CatalogService


def body(revision=0):
    return {
        "expected_revision": revision,
        "documents": {
            "answer_mode": "rag",
            "retrieval_top_k": 10,
            "retrieval_per_query_k": 30,
            "retrieval_rrf_k": 60,
            "query_expansion_enabled": False,
            "query_expansion_n": 3,
            "answer_top_k": 10,
            "rlm_max_iters": 8,
            "rlm_sub_budget": 12,
            "rlm_max_depth": 1,
            "rlm_self_consistency": 1,
            "rlm_extended_reasoning": False,
        },
        "structured": {
            "top_k_schema": 12,
            "top_k_examples": 5,
            "top_k_metrics": 8,
            "rrf_k": 60,
            "generation_candidates": 3,
            "max_refine_retries": 2,
            "grounding_min_confidence": 0.55,
        },
    }


@pytest.fixture
def policy_client(client):
    context = client.native_app.state.context
    context.container.register_instance(CanonSettings, CanonSettings(answer_mode="rlm"))
    context.container.register_instance(FlyquerySettings, FlyquerySettings())
    return client


def test_knowledge_settings_http_is_typed_strict_revisioned_and_tenant_admin_only(policy_client):
    client = policy_client
    path = "/api/v1/tenants/north/knowledge/settings"
    assert client.get(path).status_code == 401
    baseline = client.get(path, headers=bearer("viewer"))
    assert baseline.status_code == 200, baseline.text
    assert baseline.json()["origin"] == "deployment" and baseline.json()["revision"] == 0
    assert baseline.json()["documents"]["answer_mode"] == "rlm"
    for subject in ("viewer", "editor", "analyst", "outsider"):
        assert client.put(path, headers=bearer(subject), json=body()).status_code == 403
    saved = client.put(path, headers=bearer(), json=body())
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1 and saved.json()["origin"] == "organization"
    assert client.put(path, headers=bearer(), json=body()).status_code == 409
    invalid = body(1)
    invalid["documents"]["rlm_sub_budget"] = True
    assert client.put(path, headers=bearer(), json=invalid).status_code in (400, 422)
    assert client.put(path, headers=bearer(), json=body(1) | {"thread_id": "hidden"}).status_code in (
        400,
        422,
    )
    assert client.get(path, headers=bearer("outsider")).status_code == 403


def test_workspace_administrator_can_read_but_cannot_write_organization_policy(policy_client):
    client = policy_client

    async def scoped_admin():
        await client.native_app.state.context.get_bean(MembershipRepository).save(
            Membership(
                id="scoped-policy-admin",
                subject=ISSUER + "|scoped-policy-admin",
                tenant_id="north",
                workspace_id=client.workspace_id,
                role="admin",
            )
        )

    client.portal.call(scoped_admin)
    headers = bearer("scoped-policy-admin")
    path = "/api/v1/tenants/north/knowledge/settings"
    assert client.get(path, headers=headers).status_code == 200
    assert client.put(path, headers=headers, json=body()).status_code == 403


@pytest.mark.parametrize("scope", ["query:execute", "chat:use", "knowledge:search"])
@pytest.mark.parametrize("bound", ["workspace", "asset"])
def test_bound_knowledge_tokens_read_policy_without_other_knowledge_scopes_and_never_write(
    policy_client, scope, bound
):
    client = policy_client
    values = {
        "name": "Controlled policy read",
        "tenant_id": "north",
        "scopes": [scope],
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    selected = client.workspace_id
    if bound == "asset":

        async def asset():
            catalog = client.native_app.state.context.get_bean(CatalogService)
            parent = client.workspace_id
            for kind in ("project", "collection", "source", "dataset"):
                entry = await catalog.create(
                    ISSUER + "|admin", "north", kind=kind, name="Controlled " + kind, parent_id=parent
                )
                parent = entry.id
            return parent

        selected = client.portal.call(asset)
    values["workspace_ids" if bound == "workspace" else "asset_ids"] = [selected]
    issued = client.post("/api/v1/tokens", headers=bearer(), json=values)
    assert issued.status_code == 201, issued.text
    headers = {"Authorization": "Bearer " + issued.json()["token"]}
    path = "/api/v1/tenants/north/knowledge/settings"
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    assert client.put(path, headers=headers, json=body()).status_code == 403
    assert client.get("/api/v1/tenants/south/knowledge/settings", headers=headers).status_code == 403
    assert client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401
