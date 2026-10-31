# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product protocol selection is separate from portable provider controls."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from pydantic_ai.models.test import TestModel
from pyfly.agentic.models import ModelFactory
from test_service import assistants as assistants

from koinon.assistants import connections
from koinon.assistants.settings import AssistantSettings


@pytest.mark.parametrize("mode", ["default", "native", None])
def test_output_mode_is_a_typed_product_option_not_a_provider_setting(mode):
    provider = SimpleNamespace(kind="ollama", api="chat", base_url="http://127.0.0.1:11434/v1")
    resolver = connections.ConnectionResolver(
        AssistantSettings(allowed_provider_hosts=["127.0.0.1"]), ModelFactory()
    )
    values = {"max_tokens": 512, "output_mode": mode}
    options = connections.normalized_options("chat", values)
    assert options.output_mode == mode
    spec = resolver.spec(provider, "qwen2.5:3b", values)
    assert spec.options is not None
    assert "output_mode" not in spec.options.model_dump()
    assert "output_mode" not in resolver.settings_for(spec)
    assert connections.output_mode_for(provider.kind, values) == (mode or "native")


@pytest.mark.parametrize("mode", [True, "", "auto", "tool", "prompted", {}, 1])
def test_output_mode_rejects_untyped_or_unimplemented_protocols(mode):
    with pytest.raises(ValidationError):
        connections.ModelParameters.model_validate({"output_mode": mode})


def test_unset_null_and_explicit_protocol_fingerprints_preserve_legacy_identity():
    old = connections.options_fingerprint("chat", {"max_tokens": 512})
    assert connections.options_fingerprint("chat", {"max_tokens": 512, "output_mode": None}) == old
    explicit = {
        connections.options_fingerprint("chat", {"max_tokens": 512, "output_mode": value})
        for value in ("default", "native")
    }
    assert len(explicit) == 2 and old not in explicit
    assert connections.output_mode_for("openai", {}) == "default"
    assert connections.output_mode_for("anthropic", {"output_mode": "native"}) == "native"


@pytest.mark.parametrize(
    "mode,profile,rlm",
    [
        ("native", {"supports_json_schema_output": False}, False),
        ("default", {"supports_tools": False}, True),
        ("default", {"supports_tools": False, "default_structured_output_mode": "tool"}, False),
        (
            "default",
            {"supports_json_schema_output": False, "default_structured_output_mode": "native"},
            False,
        ),
    ],
)
def test_actual_model_capabilities_reject_unsupported_mode_before_dispatch(mode, profile, rlm):
    model = TestModel(profile=profile)
    with pytest.raises(ValueError, match="output mode"):
        connections.admit_output_mode(model, mode, rlm=rlm)
    assert model.last_model_request_parameters is None


def test_default_structured_output_honors_actual_profile_instead_of_assuming_tools():
    model = TestModel(
        profile={
            "supports_tools": False,
            "supports_json_schema_output": True,
            "default_structured_output_mode": "native",
        }
    )
    connections.admit_output_mode(model, "default")
    with pytest.raises(ValueError):
        connections.admit_output_mode(model, "default", rlm=True)


@pytest.mark.parametrize("mode", ["default", "native"])
async def test_agent_roundtrip_keeps_product_choice_instead_of_serializing_only_framework_options(
    assistants, mode
):
    service, _ = assistants
    provider = await service.save_provider(
        "issuer|admin",
        "north",
        {
            "name": "Local",
            "kind": "ollama",
            "base_url": "http://127.0.0.1:11434/v1",
            "model_ids": ["qwen2.5:3b"],
        },
    )
    agent = await service.save_agent(
        "issuer|admin",
        "north",
        {
            "name": "Explicit protocol",
            "provider_id": provider["id"],
            "model_id": "qwen2.5:3b",
            "model_options": {"max_tokens": 512, "output_mode": mode},
            "tools": [],
        },
    )
    assert agent["model_options"]["output_mode"] == mode
    assert "output_mode" not in agent["model_settings"]


def test_knowledge_connection_input_uses_same_typed_options_and_distinguishes_omission():
    from koinon.knowledge.connections.dtos import ConnectionInput

    fields = {"domain": "documents", "role": "documents.rlm"}
    value = ConnectionInput.model_validate({**fields, "model_options": {"output_mode": "default"}})
    assert isinstance(value.model_options, connections.ModelParameters)
    assert ConnectionInput.model_validate(fields).model_options is None
    with pytest.raises(ValidationError):
        ConnectionInput.model_validate({**fields, "model_options": {"output_mode": "tool"}})


@pytest.mark.parametrize("mode", ["default", "native"])
async def test_actual_factory_and_sdk_serialize_selected_protocol_without_provider_option_leaks(
    assistants, monkeypatch, mode
):
    import json

    import httpx2
    from pydantic import BaseModel
    from pydantic_ai import NativeOutput
    from pyfly.agentic.factory import AgentFactory

    class Outcome(BaseModel):
        value: str

    wires = []

    def respond(request):
        payload = json.loads(request.content)
        wires.append(payload)
        message = {"role": "assistant"}
        if mode == "native":
            message["content"] = '{"value":"offline"}'
            finish = "stop"
        else:
            name = payload["tools"][0]["function"]["name"]
            message["tool_calls"] = [
                {
                    "id": "actual-sdk-call",
                    "type": "function",
                    "function": {"name": name, "arguments": '{"value":"offline"}'},
                }
            ]
            finish = "tool_calls"
        return httpx2.Response(
            200,
            json={
                "id": "offline-output-mode",
                "object": "chat.completion",
                "created": 0,
                "model": "qwen2.5:3b",
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
            },
        )

    monkeypatch.setattr(
        "pydantic_ai.providers._openai_compatible.create_async_httpx2_client",
        lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(respond), trust_env=False),
    )
    resolver = connections.ConnectionResolver(
        AssistantSettings(allowed_provider_hosts=["127.0.0.1"]), ModelFactory()
    )
    provider = SimpleNamespace(
        kind="ollama",
        api="chat",
        base_url="http://127.0.0.1:11434/v1",
        checks=[],
        validated_revision=None,
        revision=1,
        model_ids=["qwen2.5:3b"],
    )
    values = {"max_tokens": 512, "output_mode": mode}
    spec = resolver.spec(provider, "qwen2.5:3b", values)
    _, context = assistants
    factory = context.get_bean(AgentFactory)
    async with resolver.models.build_with_secret(spec, "unused") as model:
        assert resolver.output_mode(provider, "qwen2.5:3b", values, model) == mode
        agent = factory.create(
            "offline-output-mode",
            model=model,
            output_type=NativeOutput(Outcome) if mode == "native" else Outcome,
            model_settings=resolver.settings_for(spec),
            model_options=spec.options,
            config=factory.runtime.config.model_copy(update={"default_temperature": None}),
            memory=None,
            auto_register=False,
        )
        result = await agent.run("Return an offline outcome")
    assert result.output.value == "offline" and len(wires) == 1
    wire = wires[0]
    assert wire["max_tokens"] == 512 and "max_completion_tokens" not in wire
    assert "output_mode" not in wire and "extra_body" not in wire and "reasoning_effort" not in wire
    assert bool(wire.get("tools")) is (mode == "default")
    assert (wire.get("response_format", {}).get("type") == "json_schema") is (mode == "native")


async def test_knowledge_http_boundary_does_not_fill_option_defaults_for_a_borrowed_role(monkeypatch):
    from unittest.mock import AsyncMock

    from starlette.requests import Request

    from koinon.knowledge.connections import controllers
    from koinon.knowledge.connections.dtos import ConnectionInput

    service = SimpleNamespace(save=AsyncMock(return_value={}))
    monkeypatch.setattr(
        controllers, "identity_from_request", lambda request: SimpleNamespace(subject="admin")
    )
    body = ConnectionInput(domain="documents", role="documents.rlm", mode="current_agent", model_options={})
    await controllers.KnowledgeConnectionsController(service).create(
        "north", body, Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    )
    assert service.save.call_args.args[2]["model_options"] == {}


def test_actual_profile_cannot_override_a_current_negative_provider_capability():
    resolver = connections.ConnectionResolver(AssistantSettings(), ModelFactory())
    provider = SimpleNamespace(
        kind="ollama",
        api="chat",
        base_url="http://127.0.0.1:11434/v1",
        revision=2,
        validated_revision=2,
        model_ids=["qwen2.5:3b"],
        checks=[
            {
                "model_id": "qwen2.5:3b",
                "capability": "tools",
                "verified": False,
                "supported": False,
                "status": "failed",
            }
        ],
    )
    model = TestModel()
    with pytest.raises(ValueError, match="capabilities"):
        resolver.output_mode(provider, "qwen2.5:3b", {"output_mode": "default"}, model, rlm=True)
    assert model.last_model_request_parameters is None


async def test_queued_answer_cannot_adopt_a_later_admin_output_mode_change(assistants, monkeypatch):
    from unittest.mock import Mock

    from pyfly.kernel import ConflictException
    from test_service import configured

    from koinon.assistants.execution import AssistantExecutor
    from koinon.assistants.queue import AssistantQueue

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    run = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "An offline question",
            "client_request_id": "mode-change",
        },
    )
    await service.save_agent(
        "issuer|admin",
        "north",
        {
            "model_options": {"max_tokens": 512, "output_mode": "default"},
        },
        agent["id"],
    )
    await context.get_bean(AssistantQueue).claim("mode-worker")
    build = Mock(side_effect=AssertionError("No model may be built from a changed queued configuration"))
    monkeypatch.setattr(ModelFactory, "build_with_secret", build)
    with pytest.raises(ConflictException) as raised:
        await context.get_bean(AssistantExecutor).generate(run["run_id"], "mode-worker")
    assert raised.value.code == "CONFIGURATION_CHANGED"
    build.assert_not_called()
