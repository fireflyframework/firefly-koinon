# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage


async def test_local_rlm_uses_context_owned_agents_and_preserves_existing_tool_protocol():
    from flycanon.config import CanonSettings
    from flycanon.core.configuration import CanonCoreConfiguration

    requests = []

    def respond(messages, info):
        requests.append(messages)
        assert info.function_tools[0].name == "python"
        assert info.allow_text_output is False
        return ModelResponse(
            parts=[TextPart("Inspecting"), ToolCallPart("python", {"code": "print(42)"}, "call-one")],
            usage=RequestUsage(input_tokens=10, output_tokens=4),
        )

    model = FunctionModel(respond)
    factory = SimpleNamespace(
        create=MagicMock(return_value=SimpleNamespace(agent=SimpleNamespace(model=model)))
    )
    settings = CanonSettings(rlm_root_model="ollama:owned-model", rlm_sub_model="ollama:owned-model")
    client = CanonCoreConfiguration().rlm_chat_client(settings, factory)
    result = await asyncio.to_thread(
        client.chat_raw,
        [{"role": "user", "content": "threshold?"}],
        "Use evidence",
        [{"name": "python", "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}}}],
    )
    assert result["stop_reason"] == "tool_use"
    assert result["content"][1] == {
        "type": "tool_use",
        "name": "python",
        "id": "call-one",
        "input": {"code": "print(42)"},
    }
    assert client.token_totals()["input_tokens"] == 10
    assert client.fork().token_totals()["input_tokens"] == 0
    assert factory.create.call_args.kwargs["model"] == "ollama:owned-model"
    assert factory.create.call_args.kwargs["auto_register"] is False


async def test_native_rlm_tool_results_and_model_overrides_are_bounded():
    from flycanon.config import CanonSettings
    from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient

    def respond(messages, info):
        returned = [
            part for message in messages for part in message.parts if isinstance(part, ToolReturnPart)
        ]
        assert returned[0].tool_name == "python" and returned[0].tool_call_id == "call-one"
        return ModelResponse(parts=[TextPart("42")])

    model = FunctionModel(respond)
    factory = SimpleNamespace(
        create=MagicMock(return_value=SimpleNamespace(agent=SimpleNamespace(model=model)))
    )
    client = NativeRlmChatClient(
        CanonSettings(rlm_root_model="ollama:owned", rlm_sub_model="ollama:owned"), factory
    )
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "call-one", "name": "python", "input": {"code": "print(42)"}}
            ],
        },
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call-one", "content": "42"}]},
    ]
    result = await asyncio.to_thread(client.chat_raw, messages, "", [])
    assert result["content"] == [{"type": "text", "text": "42"}]
    with pytest.raises(ValueError, match="configured"):
        await asyncio.to_thread(client.complete, "facts", model="anthropic:unconfigured")


async def test_local_rlm_does_not_accept_plain_text_instead_of_the_required_evidence_tool():
    from pyfly.kernel import ServiceUnavailableException

    from flycanon.config import CanonSettings
    from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient

    factory = SimpleNamespace(
        create=MagicMock(
            return_value=SimpleNamespace(
                agent=SimpleNamespace(
                    model=FunctionModel(lambda messages, info: ModelResponse(parts=[TextPart("Trust me")]))
                ),
            )
        )
    )
    client = NativeRlmChatClient(
        CanonSettings(rlm_root_model="ollama:owned", rlm_sub_model="ollama:owned"), factory
    )
    with pytest.raises(ServiceUnavailableException) as raised:
        await asyncio.to_thread(
            client.chat_raw, [{"role": "user", "content": "question"}], "", [{"name": "python"}]
        )
    assert raised.value.code == "RLM_TOOL_PROTOCOL_REQUIRED"
