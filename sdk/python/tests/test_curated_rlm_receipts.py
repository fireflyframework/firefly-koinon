# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Standalone clients preserve curated and document audit identities separately."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from koinon_sdk import DocumentKnowledgeCapabilities, RlmToolReceipt


def fixture(name):
    root = Path(__file__).resolve().parents[3]
    return json.loads((root / "sdk/contract/fixtures.json").read_text())["fixtures"][name]


def test_old_document_and_new_knowledge_scopes_are_backward_compatible():
    old = fixture("RlmToolReceipt")
    old.pop("knowledge_item_ids", None)
    assert RlmToolReceipt.model_validate(old).knowledge_item_ids == []
    raw = {**old, "source_ids": [], "knowledge_item_ids": ["canonical-item"]}
    receipt = RlmToolReceipt.model_validate(raw)
    assert receipt.source_ids == [] and receipt.knowledge_item_ids == ["canonical-item"]
    assert receipt.model_dump()["knowledge_item_ids"] == ["canonical-item"]


@pytest.mark.parametrize("value", [[], [1], ["x" * 65], ["same", "same"]])
def test_typed_knowledge_scope_rejects_invalid_or_unproven_empty_actions(value):
    with pytest.raises(ValidationError):
        RlmToolReceipt.model_validate(
            {**fixture("RlmToolReceipt"), "source_ids": [], "knowledge_item_ids": value}
        )


def test_capability_success_shape_is_typed_while_current_advertisement_stays_unqualified():
    current = fixture("DocumentKnowledgeCapabilities")
    assert DocumentKnowledgeCapabilities.model_validate(current).rlm_curated_knowledge_supported is False
    success = DocumentKnowledgeCapabilities.model_validate(
        {**current, "rlm_curated_knowledge_supported": True, "rlm_curated_knowledge_reason": None}
    )
    assert success.rlm_curated_knowledge_reason is None
    with pytest.raises(ValidationError):
        DocumentKnowledgeCapabilities.model_validate({**current, "rlm_curated_knowledge_supported": True})
