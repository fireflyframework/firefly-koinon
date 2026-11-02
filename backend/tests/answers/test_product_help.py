# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError

from koinon.answers.dtos import EvidenceAnswerPlan
from koinon.answers.help_dtos import ProductHelpContext
from koinon.answers.language import effective_language
from koinon.answers.product_help import render_product_help
from koinon.answers.rendering import render_answer


def context(**values):
    return ProductHelpContext(
        product_name="Corporate Brain",
        assistant_name="Sócrates",
        branding_revision=4,
        tools=("search_knowledge",),
        **values,
    )


def test_identity_is_trusted_product_configuration_without_knowledge_citations():
    rendered = render_product_help("identity", context(), "es")
    assert "Sócrates" in rendered.text and "Corporate Brain" in rendered.text
    assert rendered.citations == rendered.fact_ids == rendered.source_refs == ()
    assert "Soy" in rendered.text


def test_capabilities_describe_only_current_offered_tools_without_claiming_loaded_sources():
    rendered = render_product_help("capabilities", context(), "en")
    assert "search" in rendered.text.lower()
    assert "SQL" not in rendered.text and "change proposal" not in rendered.text
    assert "already indexed" not in rendered.text


@pytest.mark.parametrize(
    "language,identity,capability", [("es", "Soy", "Buscar pasajes"), ("en", "I'm", "Search passages")]
)
def test_combined_help_composes_identity_and_only_authorized_capabilities(language, identity, capability):
    plan = EvidenceAnswerPlan.model_validate(
        {"outcome": "product_help", "help_topic": "identity_and_capabilities", "language": language}
    )
    rendered = render_product_help(plan.help_topic, context(), language)
    assert identity in rendered.text and "Sócrates" in rendered.text and "Corporate Brain" in rendered.text
    assert capability in rendered.text
    assert "dataset" not in rendered.text and "conjuntos" not in rendered.text
    assert "proposal" not in rendered.text and "propuestas" not in rendered.text
    assert rendered.citations == rendered.fact_ids == rendered.source_refs == ()


def test_combined_help_without_tools_keeps_identity_and_explains_current_limit():
    restricted = context().model_copy(update={"tools": ()})
    rendered = render_product_help("identity_and_capabilities", restricted, "es")
    assert "Soy Sócrates" in rendered.text
    assert "No tengo herramientas de conocimiento disponibles en este contexto" in rendered.text
    assert "Buscar pasajes" not in rendered.text


@pytest.mark.parametrize("topic", ["identity", "identity_and_capabilities"])
@pytest.mark.parametrize(
    "extra",
    [
        {"quotes": [{"fact_id": "x", "quote": "untrusted"}]},
        {"values": [{"fact_id": "x"}]},
        {"answer": "Invented general knowledge"},
    ],
)
def test_product_help_cannot_mix_knowledge_facts_or_free_model_prose(extra, topic):
    with pytest.raises(ValidationError):
        EvidenceAnswerPlan.model_validate({"outcome": "product_help", "help_topic": topic, **extra})


def test_product_help_requires_known_topic_and_separate_trusted_context():
    plan = EvidenceAnswerPlan.model_validate(
        {"outcome": "product_help", "help_topic": "identity", "language": "es"}
    )
    with pytest.raises(ValueError):
        render_answer(plan, (), "es")
    with pytest.raises(ValidationError):
        EvidenceAnswerPlan.model_validate({"outcome": "product_help", "help_topic": "world_knowledge"})


@pytest.mark.parametrize(
    "turn,preferences,expected",
    [
        ("es", {"response_language": "en", "locale": "en-US"}, "es"),
        ("en", {"response_language": "es", "locale": "es-ES"}, "en"),
        (None, {"effective_language": "es", "response_language": "auto", "locale": "en-US"}, "es"),
        (None, {"response_language": "auto", "locale": "es-ES"}, "es"),
    ],
)
def test_current_turn_choice_overrides_profile_and_persisted_choice_survives_fallback(
    turn, preferences, expected
):
    assert effective_language(preferences, turn=turn) == expected


def test_v1_release_canonical_fields_and_hash_remain_unchanged():
    from koinon.answers.receipts import AnswerRelease, digest

    old = {
        "version": 1,
        "policy_version": "knowledge-only-v1",
        "run_id": "old-run",
        "message_id": "old-message",
        "tenant_id": "old-tenant",
        "generation_id": None,
        "publication_sequence": 2,
        "outcome": "refused",
        "text_sha256": "a" * 64,
        "citations_sha256": "b" * 64,
        "artifacts_sha256": "c" * 64,
        "policy_sha256": "d" * 64,
        "fact_ids": [],
        "result_pins": [],
        "source_refs": [],
        "created_at": "2026-10-31T00:00:00Z",
    }
    assert AnswerRelease.model_validate(old).model_dump(mode="json") == old
    assert digest(AnswerRelease.model_validate(old).model_dump(mode="json")) == digest(old)
