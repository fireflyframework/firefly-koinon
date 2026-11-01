# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError

from koinon.answers.dtos import EvidenceAnswerPlan
from koinon.answers.rendering import render_answer
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.answer_evidence import AnswerFact


def facts():
    ref = SourceReference(
        id="source-ref",
        asset_id="document",
        title="Maintenance policy",
        kind="document",
        chunk_id="chunk",
        used_revision="chunk-sha256:" + "a" * 64,
        quote="The approved maintenance window is Tuesday at 09:00 UTC.",
    )
    return (
        AnswerFact("quote-fact", "current-result", "quote", ref.title, (ref,), text=ref.quote),
        AnswerFact(
            "cell-fact", "current-query", "cell", "Employee count", (ref,), value=42, lineage_sha256="b" * 64
        ),
    )


def test_exact_source_quote_and_typed_value_form_a_readable_answer_with_real_citations():
    plan = EvidenceAnswerPlan.model_validate(
        {
            "outcome": "answer",
            "quotes": [{"fact_id": "quote-fact", "quote": "Tuesday at 09:00 UTC"}],
            "values": [{"fact_id": "cell-fact"}],
        }
    )
    answer = render_answer(plan, facts(), "en")
    assert "Tuesday at 09:00 UTC" in answer.text and "Employee count: 42" in answer.text
    assert answer.fact_ids == ("quote-fact", "cell-fact")
    assert {citation["asset_id"] for citation in answer.citations} == {"document"}


@pytest.mark.parametrize("extra", ["answer", "claims", "reasoning", "explanation"])
def test_model_has_no_arbitrary_factual_prose_field(extra):
    with pytest.raises(ValidationError):
        EvidenceAnswerPlan.model_validate(
            {
                "outcome": "answer",
                "quotes": [{"fact_id": "quote-fact", "quote": "Tuesday"}],
                extra: "Jupiter has 999 moons",
            }
        )


@pytest.mark.parametrize(
    "quotes,values",
    [
        ([{"fact_id": "forged", "quote": "Tuesday"}], []),
        ([{"fact_id": "quote-fact", "quote": "Jupiter has 999 moons"}], []),
        ([{"fact_id": "quote-fact", "quote": "Tuesday"}, {"fact_id": "forged", "quote": "Unsupported"}], []),
        ([], [{"fact_id": "quote-fact"}]),
        ([{"fact_id": "cell-fact", "quote": "42"}], []),
    ],
)
def test_whole_plan_fails_closed_for_missing_mixed_or_wrong_kind_evidence(quotes, values):
    plan = EvidenceAnswerPlan.model_validate({"outcome": "answer", "quotes": quotes, "values": values})
    with pytest.raises(ValueError):
        render_answer(plan, facts(), "en")


def test_selected_cell_has_no_model_value_or_unsupported_coefficient():
    with pytest.raises(ValidationError):
        EvidenceAnswerPlan.model_validate(
            {"outcome": "answer", "values": [{"fact_id": "cell-fact", "value": 999}]}
        )


def test_insufficiency_has_fixed_localized_text_without_model_claims():
    plan = EvidenceAnswerPlan.model_validate({"outcome": "insufficient_evidence"})
    answer = render_answer(plan, (), "es")
    assert "conocimiento" in answer.text and answer.fact_ids == () and answer.citations == ()


def test_an_answer_requires_at_least_one_current_evidence_selection():
    with pytest.raises(ValidationError):
        EvidenceAnswerPlan.model_validate({"outcome": "answer"})
