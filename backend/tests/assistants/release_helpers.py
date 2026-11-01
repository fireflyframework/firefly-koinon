# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Use the native generation and queue transaction in evidence-bearing test fixtures."""

from koinon.answers.dtos import EvidenceAnswerPlan
from koinon.assistants.memory.service import PersonalConversationMemory
from koinon.assistants.queue import AssistantQueue


async def seal_first_quote(context, run, worker_id):
    queue = context.get_bean(AssistantQueue)
    generation = await queue.begin_generation(
        run.id, worker_id, model_id="controlled", model_class="controlled", api="chat"
    )
    await context.get_bean(PersonalConversationMemory).build(run, generation_id=generation)
    facts = await queue.fact_pool(run.id, worker_id)
    assert facts and facts[0].kind == "quote"
    await queue.release_answer(
        run.id,
        worker_id,
        EvidenceAnswerPlan(outcome="answer", quotes=[{"fact_id": facts[0].id, "quote": facts[0].text}]),
        "en",
    )
