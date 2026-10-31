# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A supported success shape is typed without prematurely advertising model qualification."""

import pytest
from pydantic import ValidationError

from koinon.organization_knowledge.dtos import DocumentKnowledgeCapabilities
from koinon.organization_knowledge.service import capabilities


def test_coherent_success_shape_does_not_change_unqualified_advertisement():
    existing = capabilities().documents
    assert existing.rlm_curated_knowledge_supported is False
    assert existing.rlm_curated_knowledge_reason == "KNOWLEDGE_RLM_UNQUALIFIED"
    success = DocumentKnowledgeCapabilities.model_validate(
        {
            **existing.model_dump(),
            "rlm_curated_knowledge_supported": True,
            "rlm_curated_knowledge_reason": None,
        }
    )
    assert success.rlm_curated_knowledge_supported and success.rlm_curated_knowledge_reason is None


@pytest.mark.parametrize("supported,reason", [(True, "KNOWLEDGE_RLM_UNQUALIFIED"), (False, None)])
def test_capability_cannot_publish_a_contradictory_reason(supported, reason):
    with pytest.raises(ValidationError):
        DocumentKnowledgeCapabilities.model_validate(
            {
                **capabilities().documents.model_dump(),
                "rlm_curated_knowledge_supported": supported,
                "rlm_curated_knowledge_reason": reason,
            }
        )
