# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError

from koinon_sdk.curated import DocumentEvidence, KnowledgeConfirmation, KnowledgeIntentInput, StructuredEvidence
from koinon_sdk.sharing import ShareCreate


@pytest.mark.parametrize("evidence_type,kind", [(DocumentEvidence, "document_passage"), (StructuredEvidence, "structured_snapshot")])
def test_memory_evidence_preserves_absence_and_explicit_historical_basis(evidence_type, kind):
    source = {"id": "source", "kind": "document" if kind == "document_passage" else "dataset",
              "asset_id": "asset", "title": "Recorded evidence", "availability": "available"}
    historical_wire = {"kind": kind, "source": source}
    historical = evidence_type.model_validate(historical_wire)
    assert "basis" not in historical.model_dump(mode="json")
    remembered = evidence_type.model_validate({**historical_wire, "basis": "remembered_context"})
    assert remembered.model_dump(mode="json")["basis"] == "remembered_context"


@pytest.mark.parametrize("invalid", ["true", 1, None])
def test_remembered_context_sharing_consent_is_an_explicit_boolean(invalid):
    with pytest.raises(ValidationError):
        ShareCreate.model_validate({"review_id": "review", "expected_revision": "a" * 64,
                                    "include_remembered_context": invalid})
    with pytest.raises(ValidationError) as failure:
        KnowledgeConfirmation.model_validate({"confirm": True, "expected_revision": 1,
                                               "authorization_digest": "a" * 64,
                                               "include_remembered_context": invalid})
    assert [error["loc"] for error in failure.value.errors()] == [("include_remembered_context",)]


def test_a_partial_memory_policy_does_not_invent_unspecified_limits():
    from koinon_sdk import OrganizationChatSettingsInput, OrganizationMemoryPolicyInput

    change = OrganizationChatSettingsInput(default_agent_id="agent", expected_revision=3,
        memory=OrganizationMemoryPolicyInput(max_history_messages=10))
    assert change.model_dump(exclude_unset=True)["memory"] == {"max_history_messages": 10}
    assert "include_remembered_context" in KnowledgeIntentInput.model_fields
