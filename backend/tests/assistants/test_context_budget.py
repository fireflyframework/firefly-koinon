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
    now = datetime.now(UTC)
    old = SimpleNamespace(
        id="old",
        scope={},
        created_at=now - timedelta(seconds=2),
        user_message_id="old-user",
        message_id="old-answer",
    )
    recent = SimpleNamespace(
        id="recent",
        scope={},
        created_at=now - timedelta(seconds=1),
        user_message_id="recent-user",
        message_id="recent-answer",
    )
    messages = {
        "old-user": "old " * 200,
        "old-answer": "older answer",
        "recent-user": "Current question",
        "recent-answer": "Current answer",
    }

    async def message(identifier):
        return SimpleNamespace(text=messages[identifier], answer_policy=policy)

    executor = object.__new__(AssistantExecutor)
    executor.assistants = SimpleNamespace(
        _attachment_access=lambda: None,
        settings=SimpleNamespace(max_history_messages=40, max_history_tokens=256),
        threads=SimpleNamespace(find_by_id=AsyncMock(return_value=SimpleNamespace(subject="issuer|reader"))),
        runs=SimpleNamespace(find_all=AsyncMock(return_value=[old, recent])),
        authorize_results=AsyncMock(),
        message_repository=SimpleNamespace(find_by_id=message),
    )
    history = await executor.history(
        SimpleNamespace(thread_id="thread", tenant_id="tenant", scope={}, created_at=now)
    )
    assert len(history) == 2
    assert history[0].parts[0].content == "Current question"
    assert "Current answer" not in history[1].parts[0].content
    if policy.get("outcome") in {"refused", "review_required"}:
        from koinon.assistants.grounding import refusal_message

        code = "REVIEW_REQUIRED" if policy["outcome"] == "review_required" else "KNOWLEDGE_ONLY"
        assert history[1].parts[0].content == refusal_message("en-US", code)
    else:
        assert "Retrieve the selected sources again" in history[1].parts[0].content
    assert messages["recent-answer"] == "Current answer"
    executor.assistants.authorize_results.assert_any_await("issuer|reader", "tenant", "recent")


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
