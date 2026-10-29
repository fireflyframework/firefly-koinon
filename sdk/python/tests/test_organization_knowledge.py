# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from koinon_sdk import (
    AnswerAudit,
    DocumentKnowledgeCapabilities,
    DocumentKnowledgeSettings,
    KoinonClient,
    OrganizationKnowledgeSettings,
    OrganizationKnowledgeSettingsInput,
    OrganizationKnowledgeSnapshot,
    QueryResponse,
    SearchResponse,
    StructuredKnowledgeSettings,
)


def fixtures():
    return json.loads((Path(__file__).resolve().parents[2] / "contract/fixtures.json").read_text())[
        "fixtures"
    ]


async def test_policy_get_and_update_are_typed_tenant_only_and_revision_bound():
    calls = []
    value = fixtures()["OrganizationKnowledgeSettings"]

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=value)

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "fixture", transport=httpx.MockTransport(handle)
    ) as client:
        current = await client.organization_knowledge_settings("north/one")
        assert isinstance(current, OrganizationKnowledgeSettings)
        assert isinstance(current.documents, DocumentKnowledgeSettings)
        assert isinstance(current.structured, StructuredKnowledgeSettings)
        assert current.capabilities.documents.rlm_model_role == "documents.rlm"
        assert current.capabilities.documents.rlm_curated_knowledge_supported is False
        assert current.capabilities.documents.rlm_recorded_views_required is True
        assert current.capabilities.documents.rlm_recorded_views_reason == "RLM_DOCUMENT_VIEWS_REQUIRED"
        assert current.capabilities.documents.bounds.rlm_max_iters.maximum >= 1
        request = OrganizationKnowledgeSettingsInput(
            expected_revision=current.revision, documents=current.documents, structured=current.structured
        )
        updated = await client.update_organization_knowledge_settings("north/one", request)
        assert updated.revision == current.revision
    assert [(call.method, call.url.raw_path) for call in calls] == [
        ("GET", b"/api/v1/tenants/north%2Fone/knowledge/settings"),
        ("PUT", b"/api/v1/tenants/north%2Fone/knowledge/settings"),
    ]
    assert json.loads(calls[1].content) == request.model_dump(mode="json")
    assert calls[1].headers["authorization"] == "Bearer fixture"


@pytest.mark.parametrize(
    "field,value",
    [
        ("retrieval_top_k", True),
        ("answer_mode", "unsupported"),
        ("rlm_max_iters", 65),
        ("query_expansion_enabled", "true"),
        ("storage_backend", "s3"),
    ],
)
def test_document_policy_remains_strict_in_standalone_sdk(field, value):
    raw = fixtures()["DocumentKnowledgeSettings"]
    raw[field] = value
    with pytest.raises(ValidationError):
        DocumentKnowledgeSettings.model_validate(raw)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 1.1, True])
def test_structured_confidence_is_finite_numeric_and_bounded(value):
    raw = fixtures()["StructuredKnowledgeSettings"]
    raw["grounding_min_confidence"] = value
    with pytest.raises(ValidationError):
        StructuredKnowledgeSettings.model_validate(raw)


def test_update_rejects_unknown_fields_and_boolean_revision():
    raw = fixtures()["OrganizationKnowledgeSettingsInput"]
    for changes in ({"expected_revision": True}, {"workspace_id": "not-an-organization-write"}):
        with pytest.raises(ValidationError):
            OrganizationKnowledgeSettingsInput.model_validate({**raw, **changes})


def test_recorded_view_prerequisite_is_an_exact_capability():
    raw = fixtures()["DocumentKnowledgeCapabilities"]
    with pytest.raises(ValidationError):
        DocumentKnowledgeCapabilities.model_validate({**raw, "rlm_recorded_views_required": False})


def test_applied_snapshot_is_typed_and_missing_historical_metadata_stays_unknown():
    raw = fixtures()["OrganizationKnowledgeSnapshot"]
    for model, body in (
        (SearchResponse, {"hits": []}),
        (QueryResponse, {"query_id": "query", "execution_status": "OK"}),
        (AnswerAudit, {"run_id": "old", "provenance_status": "not_recorded"}),
    ):
        assert model.model_validate(body).knowledge_settings_snapshot is None
        snapshot = model.model_validate(
            {**body, "knowledge_settings_snapshot": raw}
        ).knowledge_settings_snapshot
        assert isinstance(snapshot, OrganizationKnowledgeSnapshot)
        assert snapshot.digest == raw["digest"]
        assert snapshot.documents.answer_mode == raw["documents"]["answer_mode"]
