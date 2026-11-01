# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from koinon.answers.dtos import EvidenceAnswerPlan
from koinon.answers.private import verified_private_facts
from koinon.answers.rendering import render_answer
from koinon.assistants.attachment_input import prepare_attachment_input
from koinon.knowledge.attachments.ports import AttachmentContent, AttachmentRef, PrivateTextUnit


async def extracted():
    ref = AttachmentRef(
        "private-file",
        "tenant",
        "thread",
        "issuer|owner",
        "a" * 64,
        1,
        "Private notes.txt",
        "text/plain",
        "document",
        50,
        datetime.now(UTC) + timedelta(hours=1),
    )
    text = "The recorded threshold is twelve."
    unit = PrivateTextUnit("chunk-one", text, sha256(text.encode()).hexdigest(), 2)
    access = SimpleNamespace(
        content_for_model=AsyncMock(
            return_value=(AttachmentContent(ref, text="untrusted display header", text_units=(unit,)),)
        )
    )
    value = await prepare_attachment_input(
        access,
        subject=ref.subject,
        tenant_id=ref.tenant_id,
        thread_id=ref.thread_id,
        refs=(ref,),
        question="UNTRUSTED_USER_QUESTION",
        fits_text=AsyncMock(return_value=True),
        input_modalities=["text"],
    )
    facts = tuple(replace(fact, result_id="private-result") for fact in value.facts)
    rows = (SimpleNamespace(id="private-result", kind="attachment", payload={"data": value.evidence}),)
    return ref, value, facts, rows


async def test_private_fact_is_exact_extracted_unit_not_question_or_display_header():
    ref, value, facts, rows = await extracted()
    verified = verified_private_facts(facts, rows, (ref,))
    assert len(verified) == 1 and verified[0].text == "The recorded threshold is twelve."
    assert "UNTRUSTED_USER_QUESTION" not in str(value.evidence)
    assert "The recorded threshold" not in str(value.evidence)
    assert "untrusted display header" not in value.prompt
    plan = EvidenceAnswerPlan(
        outcome="answer", quotes=[{"fact_id": verified[0].id, "quote": "threshold is twelve"}]
    )
    rendered = render_answer(plan, verified, "en", private_fact_ids=frozenset(fact.id for fact in verified))
    assert "Private notes.txt" in rendered.text and "threshold is twelve" in rendered.text
    assert rendered.source_refs == ()


@pytest.mark.parametrize("case", ["text", "filename", "result", "expired", "revision"])
async def test_private_fact_release_requires_current_exact_unit_and_selection(case):
    ref, _, facts, rows = await extracted()
    refs = (ref,)
    if case == "text":
        facts = (replace(facts[0], text="UNSUPPORTED_MODEL_CLAIM"),)
    if case == "filename":
        facts = (replace(facts[0], label="Fabricated source"),)
    if case == "result":
        facts = (replace(facts[0], result_id="another-run"),)
    if case == "expired":
        refs = ()
    if case == "revision":
        refs = (replace(ref, revision=2),)
    with pytest.raises(ValueError):
        verified_private_facts(facts, rows, refs)
