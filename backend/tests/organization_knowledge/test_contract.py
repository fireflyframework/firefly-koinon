# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from importlib import import_module

import pytest
from pydantic import ValidationError


def documents():
    return {
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
    }


def structured():
    return {
        "top_k_schema": 12,
        "top_k_examples": 5,
        "top_k_metrics": 8,
        "rrf_k": 60,
        "generation_candidates": 3,
        "max_refine_retries": 2,
        "grounding_min_confidence": 0.55,
    }


def input_policy():
    return {"expected_revision": 0, "documents": documents(), "structured": structured()}


def contract():
    return import_module("koinon.organization_knowledge.dtos")


def test_full_input_and_nested_policy_are_concrete_strict_and_immutable():
    dto = contract()
    parsed = dto.OrganizationKnowledgeSettingsInput.model_validate(input_policy())
    assert parsed.documents.answer_mode == "rag"
    assert parsed.structured.grounding_min_confidence == 0.55
    for target in (parsed, parsed.documents, parsed.structured):
        field = next(iter(type(target).model_fields))
        with pytest.raises(ValidationError):
            setattr(target, field, getattr(target, field))
    for path in ((), ("documents",), ("structured",)):
        for mutation in ("unknown", "missing"):
            value = deepcopy(input_policy())
            selected = value if not path else value[path[0]]
            if mutation == "unknown":
                selected["hidden"] = True
            else:
                selected.pop(next(iter(selected)))
            with pytest.raises(ValidationError):
                dto.OrganizationKnowledgeSettingsInput.model_validate(value)


@pytest.mark.parametrize(
    "name,minimum,maximum",
    [
        ("retrieval_top_k", 1, 200),
        ("retrieval_per_query_k", 1, 500),
        ("retrieval_rrf_k", 1, 1000),
        ("query_expansion_n", 1, 10),
        ("answer_top_k", 1, 40),
        ("rlm_max_iters", 1, 64),
        ("rlm_sub_budget", 0, 128),
        ("rlm_max_depth", 0, 8),
        ("rlm_self_consistency", 1, 8),
    ],
)
def test_document_numeric_contract_rejects_coercion_and_outside_bounds(name, minimum, maximum):
    dto = contract()
    for invalid in (True, False, str(minimum), float(minimum), minimum - 1, maximum + 1):
        with pytest.raises(ValidationError):
            dto.DocumentKnowledgeSettings.model_validate(documents() | {name: invalid})
    for valid in (minimum, maximum):
        assert (
            getattr(dto.DocumentKnowledgeSettings.model_validate(documents() | {name: valid}), name) == valid
        )


@pytest.mark.parametrize(
    "name,minimum,maximum",
    [
        ("top_k_schema", 1, 100),
        ("top_k_examples", 0, 50),
        ("top_k_metrics", 0, 50),
        ("rrf_k", 1, 1000),
        ("generation_candidates", 1, 8),
        ("max_refine_retries", 0, 8),
    ],
)
def test_structured_numeric_contract_rejects_coercion_and_outside_bounds(name, minimum, maximum):
    dto = contract()
    for invalid in (True, str(minimum), float(minimum), minimum - 1, maximum + 1):
        with pytest.raises(ValidationError):
            dto.StructuredKnowledgeSettings.model_validate(structured() | {name: invalid})
    for valid in (minimum, maximum):
        assert (
            getattr(dto.StructuredKnowledgeSettings.model_validate(structured() | {name: valid}), name)
            == valid
        )


@pytest.mark.parametrize("invalid", [True, "0.5", float("nan"), float("inf"), float("-inf"), -0.01, 1.01])
def test_confidence_is_a_finite_number_within_unit_interval(invalid):
    with pytest.raises(ValidationError):
        contract().StructuredKnowledgeSettings.model_validate(
            structured() | {"grounding_min_confidence": invalid}
        )


@pytest.mark.parametrize("field", ["query_expansion_enabled", "rlm_extended_reasoning"])
@pytest.mark.parametrize("invalid", [1, 0, "true", "false"])
def test_document_booleans_are_not_coerced(field, invalid):
    with pytest.raises(ValidationError):
        contract().DocumentKnowledgeSettings.model_validate(documents() | {field: invalid})


@pytest.mark.parametrize("invalid", ["RAG", "unknown", "", None])
def test_answer_mode_has_no_silent_fallback(invalid):
    with pytest.raises(ValidationError):
        contract().DocumentKnowledgeSettings.model_validate(documents() | {"answer_mode": invalid})


@pytest.mark.parametrize("invalid", [True, False, "0", 0.0, -1, 2147483647])
def test_expected_revision_rejects_coercion_and_outside_cas_range(invalid):
    with pytest.raises(ValidationError):
        contract().OrganizationKnowledgeSettingsInput.model_validate(
            input_policy() | {"expected_revision": invalid}
        )
