# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from koinon.evidence.dtos import SourceReference
from koinon.knowledge.answer_evidence import AnswerFact, answer_facts
from koinon.knowledge.capture_dtos import CapturedEvidence


def document(text="Recorded policy text."):
    return SourceReference(
        id="source-reference",
        asset_id="document",
        source_id="original",
        title="Policy",
        kind="document",
        chunk_id="chunk",
        quote=text,
        used_revision="chunk-sha256:" + sha256(text.encode()).hexdigest(),
    )


def test_only_exact_current_complete_source_quotes_become_facts_never_native_answer_prose():
    source = document()
    capture = CapturedEvidence(
        {"answer": "Invented claim", "hits": [{"text": source.quote}]}, (source,), True
    )
    facts = answer_facts(capture, "current-result")
    assert len(facts) == 1 and facts[0].kind == "quote" and facts[0].text == source.quote
    assert facts[0].source_refs == (source,) and facts[0].result_id == "current-result"
    assert "Invented" not in repr(facts)
    assert facts == answer_facts(capture, "current-result")
    assert facts[0].id != answer_facts(capture, "next-result")[0].id
    with pytest.raises(FrozenInstanceError):
        facts[0].text = "changed"


def test_missing_incomplete_or_image_only_evidence_never_unlocks_fact_output():
    assert answer_facts(CapturedEvidence({"answer": "Prior answer"}, (), True), "result") == ()
    assert answer_facts(CapturedEvidence({}, (document(),), False), "result") == ()
    image = document().model_copy(update={"quote": None, "used_revision": "image-sha256:" + "a" * 64})
    assert answer_facts(CapturedEvidence({"answer": "Image interpretation"}, (image,), True), "result") == ()


def test_fact_values_are_scalar_immutable_and_never_an_arbitrary_prose_slot():
    with pytest.raises(ValueError):
        AnswerFact("a" * 64, "result", "cell", "amount", (), text="Invented", value=1)
    with pytest.raises(ValueError):
        AnswerFact("a" * 64, "result", "derived", "amount", (), value={"claim": "Invented"})
