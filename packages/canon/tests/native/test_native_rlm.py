# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
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


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("unknown", {"code": "print(42)"}),
        ("python", {"question": "threshold?", "text": "[docs[fid]]"}),
        ("python", {}),
        ("python", {"code": ""}),
        ("python", {"code": " \n\t"}),
        ("python", {"code": None}),
        ("python", {"code": 42}),
        ("python", {"code": True}),
        ("python", {"code": ["print(42)"]}),
        ("python", {"code": {"source": "print(42)"}}),
        ("python", '{"code":'),
        ("python", '["print(42)"]'),
        ("python", '"print(42)"'),
    ],
)
async def test_native_rlm_rejects_unadmitted_tools_and_invalid_code_arguments(tool_name, arguments):
    from pyfly.kernel import ServiceUnavailableException

    from flycanon.config import CanonSettings
    from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient

    model = FunctionModel(
        lambda messages, info: ModelResponse(parts=[ToolCallPart(tool_name, arguments, "invalid-call")])
    )
    factory = SimpleNamespace(
        create=MagicMock(return_value=SimpleNamespace(agent=SimpleNamespace(model=model)))
    )
    client = NativeRlmChatClient(
        CanonSettings(rlm_root_model="ollama:owned", rlm_sub_model="ollama:owned"), factory
    )
    with pytest.raises(ServiceUnavailableException) as raised:
        await asyncio.to_thread(
            client.chat_raw, [{"role": "user", "content": "question"}], "", [{"name": "python"}]
        )
    assert raised.value.code == "RLM_TOOL_PROTOCOL_REQUIRED"


async def test_native_rlm_rejects_a_malformed_later_call_before_returning_any_code():
    from pyfly.kernel import ServiceUnavailableException

    from flycanon.config import CanonSettings
    from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient

    model = FunctionModel(
        lambda messages, info: ModelResponse(
            parts=[
                ToolCallPart("python", {"code": "print(42)"}, "valid-call"),
                ToolCallPart("python", {"question": "threshold?"}, "invalid-call"),
            ]
        )
    )
    factory = SimpleNamespace(
        create=MagicMock(return_value=SimpleNamespace(agent=SimpleNamespace(model=model)))
    )
    client = NativeRlmChatClient(
        CanonSettings(rlm_root_model="ollama:owned", rlm_sub_model="ollama:owned"), factory
    )
    with pytest.raises(ServiceUnavailableException) as raised:
        await asyncio.to_thread(
            client.chat_raw, [{"role": "user", "content": "question"}], "", [{"name": "python"}]
        )
    assert raised.value.code == "RLM_TOOL_PROTOCOL_REQUIRED"


async def test_native_rlm_preserves_valid_json_code_without_coercion():
    from flycanon.config import CanonSettings
    from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient

    model = FunctionModel(
        lambda messages, info: ModelResponse(
            parts=[ToolCallPart("python", '{"code":"\\nprint(42)\\n"}', "valid-call")]
        )
    )
    factory = SimpleNamespace(
        create=MagicMock(return_value=SimpleNamespace(agent=SimpleNamespace(model=model)))
    )
    client = NativeRlmChatClient(
        CanonSettings(rlm_root_model="ollama:owned", rlm_sub_model="ollama:owned"), factory
    )
    response = await asyncio.to_thread(
        client.chat_raw, [{"role": "user", "content": "question"}], "", [{"name": "python"}]
    )
    assert response["content"] == [
        {"type": "tool_use", "name": "python", "id": "valid-call", "input": {"code": "\nprint(42)\n"}}
    ]


def _engine_client(respond):
    from flycanon.config import CanonSettings
    from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient

    model = FunctionModel(respond)
    factory = SimpleNamespace(
        create=MagicMock(return_value=SimpleNamespace(agent=SimpleNamespace(model=model)))
    )
    return NativeRlmChatClient(
        CanonSettings(rlm_root_model="ollama:owned", rlm_sub_model="ollama:owned"), factory
    )


class _ProtocolObserver:
    def __init__(self):
        self.stages = []
        self.authorizations = 0

    async def authorize(self):
        self.authorizations += 1

    def document_sync(self, stage, content, sources, scope):
        self.stages.append(stage)

    def document_tool_start(self, scope):
        pass

    def document_tool(self, receipt, scope):
        pass


async def _observed_text_run(session, observer):
    from flycanon.core.services.query import provenance

    with provenance.observe(observer, tenant_id="fixture", workspace_id="workspace", actor="owner"):
        provenance.current().source_ids.add("fixture-text")
        return await asyncio.to_thread(
            provenance.worker(session.run_over_text), "What is recorded?", "Recorded scalar: 42"
        )


@pytest.mark.parametrize(
    "invalid",
    [
        TextPart("```python\nopen('/etc/passwd')\n```"),
        ToolCallPart("python", {"question": "What is recorded?"}, "missing-code"),
        ToolCallPart("python", '{"code":', "malformed-json"),
        ToolCallPart("unknown", {"code": "open('/etc/passwd')"}, "unadmitted-tool"),
    ],
)
@pytest.mark.parametrize("sandbox", ["inprocess", "subprocess"])
async def test_native_engine_corrects_protocol_within_existing_turn_budget(invalid, sandbox):
    from flycanon.core.services.query.rlm.session import RLMSession

    requests, executed = [], []

    def respond(messages, info):
        requests.append(messages)
        assert [tool.name for tool in info.function_tools] == ["python"]
        parts = [invalid] if len(requests) == 1 else [
            ToolCallPart("python", {"code": "final(text.rsplit(': ', 1)[1])"}, "valid-code")
        ]
        return ModelResponse(parts=parts, usage=RequestUsage(input_tokens=10, output_tokens=2))

    class ObservedSession(RLMSession):
        def _run_block(self, code, runner, docs, question):
            executed.append(code)
            return super()._run_block(code, runner, docs, question)

    client, observer = _engine_client(respond), _ProtocolObserver()
    session = ObservedSession(client, max_iters=2, sub_budget=0, sandbox_mode=sandbox)
    assert await _observed_text_run(session, observer) == ("42", [], False)
    assert session.turns == len(requests) == observer.authorizations == 2
    assert observer.stages == ["rlm.root", "rlm.root"]
    assert executed == ["final(text.rsplit(': ', 1)[1])"]
    assert not any(isinstance(message, ModelResponse) for message in requests[1])
    correction = requests[1][-1].parts[0]
    assert isinstance(correction, UserPromptPart)
    assert "python" in correction.content and "code" in correction.content
    assert "open('/etc/passwd')" not in correction.content
    assert client.token_totals()["input_tokens"] == 20
    assert client.token_totals()["output_tokens"] == 4


@pytest.mark.parametrize("max_iters", [1, 3])
async def test_native_engine_exhausted_protocol_budget_never_executes_or_forces_final(max_iters):
    from pyfly.kernel import ServiceUnavailableException

    from flycanon.core.services.query.rlm.native_client import RlmToolProtocolError
    from flycanon.core.services.query.rlm.session import RLMSession

    requests, executed = [], []

    def respond(messages, info):
        requests.append(messages)
        assert [tool.name for tool in info.function_tools] == ["python", "final_answer"]
        return ModelResponse(parts=[TextPart("```python\nopen('/etc/passwd')\n```")],
                             usage=RequestUsage(input_tokens=10, output_tokens=2))

    class ObservedSession(RLMSession):
        def _run_block(self, code, runner, docs, question):
            executed.append(code)
            raise AssertionError("Rejected model output must never reach the executor")

    client, observer = _engine_client(respond), _ProtocolObserver()
    session = ObservedSession(client, max_iters=max_iters, sub_budget=0)
    with pytest.raises(ServiceUnavailableException) as raised:
        await _observed_text_run(session, observer)
    assert raised.value.code == "RLM_TOOL_PROTOCOL_REQUIRED"
    assert isinstance(raised.value, RlmToolProtocolError)
    assert len(requests) == session.turns == max_iters
    assert observer.authorizations >= max_iters
    assert observer.stages == ["rlm.root"] * max_iters
    assert executed == []
    assert client.token_totals()["input_tokens"] == 10 * max_iters


async def test_native_engine_provider_failure_is_not_a_protocol_correction():
    from pyfly.kernel import ServiceUnavailableException

    from flycanon.core.services.query.rlm.session import RLMSession

    requests = []

    def respond(messages, info):
        requests.append(messages)
        raise RuntimeError("Provider connection failed")

    observer = _ProtocolObserver()
    session = RLMSession(_engine_client(respond), max_iters=3, sub_budget=0)
    with pytest.raises(ServiceUnavailableException) as raised:
        await _observed_text_run(session, observer)
    assert raised.value.code == "RLM_PROVIDER_UNAVAILABLE"
    assert session.turns == len(requests) == 1
    assert observer.authorizations >= 1
    assert observer.stages == ["rlm.root"]


async def test_native_engine_protocol_correction_cannot_add_a_forced_final_after_valid_progress():
    from pyfly.kernel import ServiceUnavailableException

    from flycanon.core.services.query.rlm.session import RLMSession

    requests = []

    def respond(messages, info):
        requests.append(messages)
        assert [tool.name for tool in info.function_tools] == ["python", "final_answer"]
        parts = [TextPart("Use the document")] if len(requests) == 1 else [
            ToolCallPart("python", {"code": "print(text)"}, "valid-progress")
        ]
        return ModelResponse(parts=parts)

    observer = _ProtocolObserver()
    session = RLMSession(_engine_client(respond), max_iters=2, sub_budget=0)
    with pytest.raises(ServiceUnavailableException) as raised:
        await _observed_text_run(session, observer)
    assert raised.value.code == "RLM_TOOL_PROTOCOL_REQUIRED"
    assert session.turns == len(requests) == 2
    assert observer.stages == ["rlm.root", "rlm.root"]


async def test_native_engine_authorization_failure_precedes_any_model_request():
    from pyfly.kernel import ServiceUnavailableException

    from flycanon.core.services.query.rlm.session import RLMSession

    denied = ServiceUnavailableException("Evidence authorization denied", code="EVIDENCE_UNAVAILABLE")

    class DeniedObserver(_ProtocolObserver):
        async def authorize(self):
            raise denied

    def forbidden(messages, info):
        raise AssertionError("Unauthorized iteration must not call the model")

    session = RLMSession(_engine_client(forbidden), max_iters=3, sub_budget=0)
    with pytest.raises(ServiceUnavailableException) as raised:
        await _observed_text_run(session, DeniedObserver())
    assert raised.value is denied
    assert session.turns == 0
