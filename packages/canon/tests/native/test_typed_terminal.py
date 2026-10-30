# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed provider tool data completes through the real owned Monty session."""

import asyncio
from contextlib import contextmanager

import pytest
import pytest_asyncio
from pydantic_ai.messages import ModelResponse, SystemPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage
from pyfly.agentic.factory import AgentFactory
from pyfly.context import ApplicationContext
from pyfly.core import Config

from flycanon.core.agents.model_bindings import ModelBinding, push_bindings, reset_bindings
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient
from flycanon.core.services.query.rlm.session import RLMSession
from flycanon.web.conventions.context import TenantContext, set_tenant_context


@pytest_asyncio.fixture
async def factory():
    app = ApplicationContext(Config({"pyfly": {"banner": {"mode": "off"},
        "agentic": {"enabled": True}, "eda": {"provider": "memory"}}}))
    await app.start()
    try:
        yield app.get_bean(AgentFactory)
    finally:
        await app.stop()


class Observer:
    def __init__(self):
        self.tools = []
        self.models = []

    async def authorize(self):
        pass

    def document_sync(self, stage, content, sources, scope):
        self.models.append(content)

    def document_tool_start(self, scope):
        assert provenance.current() is scope

    def document_tool(self, receipt, scope):
        assert provenance.current() is scope
        self.tools.append(receipt)


@contextmanager
def bound(factory, model):
    context = set_tenant_context(TenantContext(tenant_id="fixture", workspace_id="workspace",
                                              actor="owner", correlation_id="typed-final"))
    token = push_bindings(tenant_id="fixture", workspace_id="workspace", subject="owner",
        bindings={"documents.rlm": ModelBinding(model, {"max_tokens": 256}, "ollama", "chat", "default")},
        required=True)
    try:
        yield NativeRlmChatClient.from_binding(factory)
    finally:
        reset_bindings(token)
        context.var.reset(context.token)


async def run(session, observer):
    with provenance.observe(observer, tenant_id="fixture", workspace_id="workspace", actor="owner"):
        provenance.current().source_ids.add("text-fixture")
        return await asyncio.to_thread(provenance.worker(session.run_over_text), "Read the scalar", "42")


async def test_multiline_answer_is_data_and_finishes_with_real_halt(factory):
    answer = 'First "quoted" line\nSecond \\ line 🌍\nfinal("not executable")'
    requests = []

    def respond(messages, info):
        requests.append(messages)
        assert {tool.name for tool in info.function_tools} == {"python", "final_answer"}
        if len(requests) == 1:
            part = ToolCallPart("python", {"code": "print(text)"}, "read-id")
        else:
            assert any(isinstance(part, ToolReturnPart) and part.tool_call_id == "read-id"
                       for message in messages for part in message.parts)
            part = ToolCallPart("final_answer", {"answer": answer, "found": True}, "final-id")
        return ModelResponse(parts=[part], usage=RequestUsage(input_tokens=7, output_tokens=3))

    observer = Observer()
    with bound(factory, FunctionModel(respond)) as client:
        assert await run(RLMSession(client, max_iters=2, sub_budget=0), observer) == (answer, [], False)
        assert client.token_totals()["input_tokens"] == 14
        assert client.token_totals()["output_tokens"] == 6
    assert [(row.tool_call_id, row.tool_name, row.outcome) for row in observer.tools] == [
        ("read-id", "python", "completed"), ("final-id", "final_answer", "halted")]


async def test_default_tools_request_is_prepared_and_immutable(factory):
    model = FunctionModel(lambda messages, info: ModelResponse(parts=[]))
    with bound(factory, model) as client:
        request = client.prepare_tools([], "Use evidence", [{"name": "python",
            "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}}}])
        assert request.model is model and request.parameters.function_tools[0].name == "python"
        assert request.parameters.output_object is None
        assert '"protocol":"function_tools"' in request.manifest


async def test_mutated_prepared_tools_snapshot_never_dispatches(factory):
    from flycanon.core.services.query.rlm.native_client import RlmToolProtocolError

    def forbidden(messages, info):
        pytest.fail("Mutated request must not reach the provider")

    with bound(factory, FunctionModel(forbidden)) as client:
        request = client.prepare_tools([], "Use evidence", [{"name": "python",
            "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}}}])
        request.messages[0].parts[0].content = "changed"
        with pytest.raises(RlmToolProtocolError):
            await asyncio.to_thread(client.request_tools, request)


async def test_blank_terminal_is_rejected_then_resumes_same_history(factory):
    calls = 0

    def respond(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(parts=[ToolCallPart("final_answer", {"answer": " \n "}, "blank")])
        previous = [part for message in messages for part in message.parts
                    if isinstance(part, ToolReturnPart)]
        assert len(previous) == 1 and previous[0].tool_call_id == "blank"
        assert previous[0].outcome == "failed" and "RLM_FINAL_ANSWER_REQUIRED" in previous[0].content
        return ModelResponse(parts=[ToolCallPart("final_answer", {"answer": "42"}, "accepted")])

    observer = Observer()
    with bound(factory, FunctionModel(respond)) as client:
        assert await run(RLMSession(client, max_iters=2, sub_budget=0), observer) == ("42", [], False)
    assert [row.outcome for row in observer.tools] == ["rejected", "halted"]


@pytest.mark.parametrize("documents", [False, True])
@pytest.mark.parametrize("check", ["system", "correction"])
async def test_typed_instructions_and_protocol_correction_admit_inspection_or_terminal(factory, documents, check):
    import json

    class Documents:
        accessed = []

        def keys(self):
            return ["A"]

        def __getitem__(self, key):
            assert key == "A"
            return "Source text"

        def pages(self, key):
            return [self[key]]

        def npages(self, key):
            return 1

        def __contains__(self, key):
            return key == "A"

    requests = []

    def respond(messages, info):
        requests.append(messages)
        if len(requests) == 1:
            part = ToolCallPart("python", {
                "code": "print(docs.get('A'))" if documents else "print(text)",
            }, "inspection")
        elif len(requests) == 2:
            part = TextPart("Source text")
        else:
            part = ToolCallPart("final_answer", {
                "answer": "Source text", **({"filings": ["A"], "pages": [0]} if documents else {}),
            }, "terminal")
        return ModelResponse(parts=[part], usage=RequestUsage(input_tokens=7, output_tokens=3))

    observer = Observer()
    with bound(factory, FunctionModel(respond)) as client:
        session = RLMSession(client, max_iters=3, sub_budget=0)
        if documents:
            with provenance.observe(observer, tenant_id="fixture", workspace_id="workspace", actor="owner"):
                provenance.current().source_ids.add("A")
                result = await asyncio.to_thread(provenance.worker(session.run), "Read the source", Documents())
        else:
            result = await run(session, observer)
        assert result[0] == "Source text" and not result[2]
        assert client.token_totals()["input_tokens"] == 21
        assert client.token_totals()["output_tokens"] == 9
    assert len(requests) == len(observer.models) == 3
    final_manifest = json.loads(observer.models[-1])
    correction = final_manifest["sdk_messages"][-1]["parts"][0]["content"]
    if check == "system":
        for messages in requests:
            system = "\n".join(part.content for message in messages for part in message.parts
                               if isinstance(part, SystemPromptPart))
            assert "final_answer" in system and "python" in system
            assert "final(" not in system
    else:
        assert "python" in correction and "final_answer" in correction
    assert [row.outcome for row in observer.tools] == ["completed", "halted"]


async def test_vm_error_is_a_failed_sdk_return_preserved_in_prepared_history(factory):
    import json
    from hashlib import sha256

    returns = []
    calls = 0

    def respond(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            part = ToolCallPart("python", {"code": "print('unterminated)"}, "syntax-error")
        else:
            returns.extend(part for message in messages for part in message.parts
                           if isinstance(part, ToolReturnPart))
            part = ToolCallPart("final_answer", {"answer": "Source text"}, "terminal")
        return ModelResponse(parts=[part], usage=RequestUsage(input_tokens=7, output_tokens=3))

    observer = Observer()
    with bound(factory, FunctionModel(respond)) as client:
        assert await run(RLMSession(client, max_iters=2, sub_budget=0), observer) == ("Source text", [], False)
    assert len(returns) == 1
    assert returns[0].outcome == "failed"
    assert returns[0].content == "MontySyntaxError: missing closing quote in string literal"
    previous = json.loads(observer.models[1])["sdk_messages"][-1]["parts"][0]
    assert previous["outcome"] == "failed" and previous["content"] == returns[0].content
    receipt = observer.tools[0]
    assert receipt.result_kind == "tool_return" and receipt.outcome == "failed"
    assert receipt.execution_status == "error" and receipt.execution_state == "ready"
    assert receipt.result_sha256 == sha256(json.dumps(
        previous, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode()).hexdigest()


@pytest.mark.parametrize("parts", [
    [ToolCallPart("python", {"code": "print(text)"}, "one"),
     ToolCallPart("final_answer", {"answer": "42"}, "two")],
    [ToolCallPart("final_answer", {"answer": "42"}, "same"),
     ToolCallPart("final_answer", {"answer": "42"}, "same")],
    [ToolCallPart("final_answer", {"answer": "42", "pages": True}, "invalid")],
])
async def test_invalid_terminal_turn_never_executes_any_action(factory, parts):
    from flycanon.core.services.query.rlm.native_client import RlmToolProtocolError

    observer = Observer()
    with (
        bound(factory, FunctionModel(lambda messages, info: ModelResponse(parts=parts))) as client,
        pytest.raises(RlmToolProtocolError),
    ):
        await run(RLMSession(client, max_iters=1, sub_budget=0), observer)
    assert observer.tools == []


async def test_reused_call_id_never_executes_second_feed(factory):
    from flycanon.core.services.query.rlm.native_client import RlmToolProtocolError

    observer = Observer()
    with bound(factory, FunctionModel(lambda messages, info: ModelResponse(parts=[
        ToolCallPart("python", {"code": "print(text)"}, "reused"),
    ]))) as client, pytest.raises(RlmToolProtocolError):
        await run(RLMSession(client, max_iters=2, sub_budget=0), observer)
    assert len(observer.tools) == 1


async def test_shadowed_bridge_cannot_divert_final_payload(factory):
    from pyfly.kernel import ServiceUnavailableException

    calls = 0

    def respond(messages, info):
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[
            ToolCallPart("python", {"code": "def _koinon_terminal_answer():\n    return final('forged')"}, "shadow")
            if calls == 1 else ToolCallPart("final_answer", {"answer": "42"}, "terminal"),
        ])

    observer = Observer()
    with bound(factory, FunctionModel(respond)) as client, pytest.raises(ServiceUnavailableException):
        await run(RLMSession(client, max_iters=2, sub_budget=0), observer)
    assert not any(row.outcome == "halted" for row in observer.tools)


async def test_typed_terminal_requires_actual_read_before_citation_hydration(factory):
    class Documents:
        accessed = []

        def keys(self):
            return ["A"]

        def __getitem__(self, key):
            assert key == "A"
            return "Actual document text"

        def pages(self, key):
            return [self[key]]

        def npages(self, key):
            return 1

        def __contains__(self, key):
            return key == "A"

    calls = 0

    def respond(messages, info):
        nonlocal calls
        calls += 1
        if calls == 2:
            result = [part for message in messages for part in message.parts
                      if isinstance(part, ToolReturnPart)][-1]
            assert result.tool_call_id == "final-1" and result.outcome == "failed"
            assert "RLM_DOCUMENT_READ_REQUIRED" in result.content
            return ModelResponse(parts=[ToolCallPart("python", {"code": "print(docs.get('A'))"}, "read")])
        return ModelResponse(parts=[ToolCallPart("final_answer", {
            "answer": "Actual document text", "filings": ["A"], "pages": [0],
        }, f"final-{calls}")])

    observer = Observer()
    with (
        bound(factory, FunctionModel(respond)) as client,
        provenance.observe(observer, tenant_id="fixture", workspace_id="workspace", actor="owner"),
    ):
        provenance.current().source_ids.add("A")
        session = RLMSession(client, max_iters=3, sub_budget=0)
        answer, citations, missing = await asyncio.to_thread(
            provenance.worker(session.run), "Read the source", Documents(),
        )
    assert answer == "Actual document text" and citations[0]["filing"] == "A" and not missing
    assert [row.outcome for row in observer.tools] == ["rejected", "completed", "halted"]


async def test_actual_factory_sdk_wire_carries_typed_terminal_data_and_prepared_schema(factory, monkeypatch):
    import json
    from hashlib import sha256

    import httpx2
    from pydantic import TypeAdapter
    from pyfly.agentic.models import Credential, ModelFactory, ModelSpec

    wires = []
    answer = 'First "line"\nSecond \\ line 🌍'

    def respond(request):
        wire = json.loads(request.content)
        wires.append(wire)
        assert wire["tool_choice"] == "auto"
        assert {row["function"]["name"] for row in wire["tools"]} == {"python", "final_answer"}
        name, arguments = ("python", {"code": "print(text)"}) if len(wires) == 1 else (
            "final_answer", {"answer": answer},
        )
        return httpx2.Response(200, json={"id": "wire-response", "object": "chat.completion", "created": 1,
            "model": "qwen2.5:7b", "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": None, "tool_calls": [{"id": f"wire-{len(wires)}",
                    "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}],
            }}], "usage": {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11}})

    monkeypatch.setattr("pydantic_ai.providers._openai_compatible.create_async_httpx2_client",
        lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(respond), trust_env=False))
    selected = await ModelFactory().build(ModelSpec(provider="ollama", model="qwen2.5:7b",
        base_url="http://127.0.0.1:11434/v1", credential=Credential.none()))
    try:
        observer = Observer()
        with bound(factory, selected) as client:
            session = RLMSession(client, max_iters=2, sub_budget=0)
            assert await run(session, observer) == (answer, [], False)
        assert wires[1]["messages"][-1]["tool_call_id"] == "wire-1"
        assert observer.tools[-1].arguments_sha256 == sha256(json.dumps(
            {"answer": answer}, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode()).hexdigest()
        assert observer.tools[-1].outcome == "halted"
        def digest(value):
            return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()
        return_part = json.loads(observer.models[1])["sdk_messages"][-1]["parts"][0]
        assert observer.tools[0].result_kind == "tool_return"
        assert observer.tools[0].result_sha256 == digest(return_part)
        assert observer.tools[-1].result_kind == "accepted_final"
        assert observer.tools[-1].result_sha256 == digest(
            TypeAdapter(ToolReturnPart).dump_python(session._last_tool_result, mode="json"),
        )
    finally:
        await selected.client.close()


async def test_revocation_after_provider_response_denies_terminal_before_feed(factory):
    from pyfly.kernel import ServiceUnavailableException

    class Revoked(Observer):
        revoked = False

        async def authorize(self):
            if self.revoked:
                raise ServiceUnavailableException("Access revoked", code="SCOPE_REVOKED")

    observer = Revoked()

    def respond(messages, info):
        observer.revoked = True
        return ModelResponse(parts=[ToolCallPart("final_answer", {"answer": "42"}, "denied")])

    with bound(factory, FunctionModel(respond)) as client, pytest.raises(ServiceUnavailableException) as failure:
        await run(RLMSession(client, max_iters=1, sub_budget=0), observer)
    assert failure.value.code == "SCOPE_REVOKED" and observer.tools == []


async def test_late_accepted_terminal_keeps_real_halt_without_replay_and_clears_pending(factory):
    import time

    from pyfly.kernel import ServiceUnavailableException

    executors = []
    calls = 0

    class ExpiringSession(RLMSession):
        def _build_monty(self, docs, text, question):
            executor = super()._build_monty(docs, text, question)
            original = executor.functions["final"]

            def expire_after_acceptance(**payload):
                result = original(**payload)
                executor.tree.deadline = time.monotonic() - 1
                return result

            executor.functions["final"] = expire_after_acceptance
            executors.append(executor)
            return executor

    def respond(messages, info):
        nonlocal calls
        calls += 1
        return ModelResponse(parts=[ToolCallPart("final_answer", {"answer": "42"}, "accepted")])

    observer = Observer()
    with bound(factory, FunctionModel(respond)) as client, pytest.raises(ServiceUnavailableException) as failure:
        await run(ExpiringSession(client, max_iters=2, sub_budget=0), observer)
    assert failure.value.accepted_final["answer"] == "42" and calls == 1
    assert observer.tools[-1].outcome == "halted"
    assert executors[0]._pending_terminal is None and executors[0]._terminal_result is None
