# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import InvalidRequestException

from koinon.assistants.execution import AssistantExecutor


@pytest.mark.parametrize(
    "policy", [{}, {"outcome": "grounded"}, {"outcome": "refused"}, {"outcome": "review_required"}]
)
async def test_native_memory_preserves_whole_recent_turns_within_token_budget(policy):
    from koinon.assistants.memory.repositories import MemoryCandidate
    from koinon.assistants.memory.service import PersonalConversationMemory

    now = datetime.now(UTC)
    candidates = tuple(
        MemoryCandidate(
            run_id=key,
            thread_id="thread",
            folder_id=None,
            scope={},
            created_at=now - timedelta(seconds=seconds),
            user_message_id=key + "-user",
            user_text=user,
            answer_message_id=key + "-answer",
            answer_text="Current answer",
            answer_policy=policy,
            private_thread=False,
            conversation_title="Earlier chat",
            user_created_at=now - timedelta(seconds=seconds),
        )
        for key, seconds, user in [("recent", 1, "Current question"), ("old", 2, "old " * 2000)]
    )
    thread = SimpleNamespace(
        id="thread",
        subject="issuer|reader",
        tenant_id="tenant",
        folder_id=None,
        deleted_at=None,
        archived_at=None,
    )
    service = SimpleNamespace(
        _attachment_access=lambda: None,
        threads=SimpleNamespace(find_by_id=AsyncMock(return_value=thread)),
        runs=SimpleNamespace(),
        validate_scope=AsyncMock(),
        authorize_results=AsyncMock(),
        active_results=AsyncMock(return_value=[]),
        scoped=AsyncMock(return_value=SimpleNamespace(id="recent", access_token_id=None)),
    )
    memory = object.__new__(PersonalConversationMemory)
    memory.assistants = SimpleNamespace(get=lambda: service)
    memory.settings = SimpleNamespace(max_history_messages=40, max_history_tokens=512)
    memory.repository = SimpleNamespace(
        context=AsyncMock(return_value=(thread, None, None)),
        candidates=AsyncMock(return_value=candidates),
        generation=AsyncMock(return_value=None),
        result_window=AsyncMock(return_value=[]),
        pins_fit=AsyncMock(return_value=True),
    )
    executor = object.__new__(AssistantExecutor)
    executor.memory = memory
    history = await executor.history(
        SimpleNamespace(id="current", thread_id="thread", tenant_id="tenant", scope={}, created_at=now)
    )
    assert len(history) == 2
    assert "Current question" in history[0].parts[0].content
    assert "old " * 10 not in history[0].parts[0].content
    assert "Current answer" not in history[1].parts[0].content
    assert "Retrieve the selected sources again" in history[1].parts[0].content
    assert "recent-answer" in history[1].parts[0].content
    service.authorize_results.assert_any_await(
        "issuer|reader", "tenant", "recent", require_memory=False, result_rows=[]
    )


def test_current_prompt_and_tool_budget_overflow_is_explicit_and_never_truncates():
    from koinon.assistants.context_budget import history_budget

    settings = SimpleNamespace(max_context_tokens=1024, max_history_tokens=512, tool_result_tokens=128)
    question = "x" * 2000
    with pytest.raises(InvalidRequestException) as error:
        history_budget(settings, system="System", question=question, tools=[], output_tokens=64)
    assert error.value.code == "CONTEXT_BUDGET_EXCEEDED"
    assert question == "x" * 2000
    assert (
        0 <= history_budget(settings, system="System", question="Question", tools=[], output_tokens=64) <= 512
    )


def test_typed_output_schema_reserves_context_before_any_history_or_model_input():
    from koinon.answers.dtos import EvidenceAnswerPlan
    from koinon.assistants.context_budget import history_budget

    settings = SimpleNamespace(max_context_tokens=4096, max_history_tokens=4096, tool_result_tokens=128)
    plain = history_budget(settings, system="System", question="Question", tools=[], output_tokens=64)
    typed = history_budget(
        settings,
        system="System",
        question="Question",
        tools=[],
        output_tokens=64,
        output_schema=EvidenceAnswerPlan.model_json_schema(),
    )
    assert 0 <= typed < plain
    settings.max_context_tokens = plain
    with pytest.raises(InvalidRequestException):
        history_budget(
            settings,
            system="System",
            question="Question",
            tools=[],
            output_tokens=64,
            output_schema={"description": "x" * 4096},
        )
