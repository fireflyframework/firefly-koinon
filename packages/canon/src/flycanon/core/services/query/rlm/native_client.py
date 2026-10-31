# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native application-owned local models behind the retained CodeAct protocol."""

from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, cast
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError
from pydantic_ai import NativeOutput
from pydantic_ai.direct import model_request
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.output import OutputObjectDefinition
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition
from pyfly.agentic.factory import AgentFactory
from pyfly.kernel import ServiceUnavailableException

from flycanon.config import CanonSettings
from flycanon.core.agents.model_bindings import (
    BindingScope,
    binding_for,
    current_scope,
    record_agent_construction,
    stage_settings,
)
from flycanon.core.agents.provenance import settings_digest
from flycanon.core.services.query.rlm.actions import (
    NATIVE_JSON_INSTRUCTIONS,
    FinalAnswerAction,
    FinalAnswerRequiredFeedback,
    PythonAction,
    ReadRequiredFeedback,
)
from flycanon.core.services.query.rlm.chat import TokenLedger


class RlmToolProtocolError(ServiceUnavailableException):
    """Rejected native tool output; only the engine's remaining turns may correct it."""


def _protocol_error() -> RlmToolProtocolError:
    return RlmToolProtocolError(
        "The selected model returned an invalid evidence tool call. "
        "Choose a model with reliable tool calling or use the retrieval answer mode.",
        code="RLM_TOOL_PROTOCOL_REQUIRED",
    )


@dataclass(frozen=True)
class _NativeRequest:
    owner: object
    name: str
    model: Model
    messages: list[Any]
    settings: dict[str, Any]
    parameters: ModelRequestParameters
    manifest: str


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _native_manifest(messages, settings, parameters) -> str:
    digest = settings_digest(settings)
    if digest is None:
        raise ServiceUnavailableException(
            "The native action model settings cannot be verified", code="EVIDENCE_UNAVAILABLE"
        )
    history = []
    for message in messages:
        for part in message.parts:
            if isinstance(message, ModelResponse) and isinstance(part, TextPart):
                role = "assistant"
            elif isinstance(message, ModelRequest) and isinstance(part, (SystemPromptPart, UserPromptPart)):
                role = "system" if isinstance(part, SystemPromptPart) else "user"
            elif (isinstance(message, ModelRequest) and isinstance(part, RetryPromptPart)
                  and part.tool_name is None and isinstance(part.content, str)):
                history.append({"role": "user", "content": part.model_response()})
                continue
            else:
                raise _protocol_error()
            history.append({"role": role, "content": part.content})
    output = parameters.output_object
    assert output is not None
    return _canonical({
        "protocol": "native_json", "output_mode": parameters.output_mode, "messages": history,
        "sdk_messages": ModelMessagesTypeAdapter.dump_python(messages, mode="json"),
        "request_parameters": TypeAdapter(ModelRequestParameters).dump_python(parameters, mode="json"),
        "output_schema": output.json_schema,
        "output_schema_sha256": sha256(_canonical(output.json_schema).encode()).hexdigest(),
        "output_schema_name": output.name, "output_schema_strict": output.strict,
        "model_settings_sha256": digest,
        "function_tools": [tool.name for tool in parameters.function_tools],
    })


def _tools_manifest(messages, settings, parameters) -> str:
    if settings_digest(settings) is None:
        raise _protocol_error()
    return _canonical({
        "protocol": "function_tools",
        "sdk_messages": ModelMessagesTypeAdapter.dump_python(messages, mode="json"),
        "request_parameters": TypeAdapter(ModelRequestParameters).dump_python(parameters, mode="json"),
        "model_settings_sha256": settings_digest(settings),
    })


class RequiredRlmBindingClient:
    """A provider-free product bootstrap; the answer adapter borrows the request connection."""

    root_model = ""
    sub_model = ""

    def _required(self, *args, **kwargs):
        raise ServiceUnavailableException(
            "Select an authorized native connection for documents.rlm",
            code="KNOWLEDGE_MODEL_BINDING_REQUIRED",
        )

    fork = chat_raw = complete = reset_tokens = token_totals = _required


class NativeRlmChatClient:
    def __init__(self, settings: CanonSettings, factory: AgentFactory):
        self._loop = asyncio.get_running_loop()
        references = [settings.rlm_root_model, settings.rlm_sub_model]
        if any(not value.startswith("ollama:") or not value.removeprefix("ollama:") for value in references):
            raise ValueError("Both native local RLM models must name configured ollama models")
        self.root_model, self.sub_model = [value.removeprefix("ollama:") for value in references]
        self._agents = {
            name: factory.create("canon-rlm-local-" + name, model="ollama:" + name, auto_register=False)
            for name in dict.fromkeys((self.root_model, self.sub_model))
        }
        self._ledger = TokenLedger(dict.fromkeys(self._agents, (0.0, 0.0)))
        self._borrowed = False
        self._binding_scope: BindingScope | None = None
        self.action_protocol = "function_tools"
        self._tool_ids: frozenset[str] = frozenset()

    @classmethod
    def from_binding(cls, factory: AgentFactory) -> NativeRlmChatClient:
        scope = current_scope()
        binding = binding_for("documents.rlm")
        if scope is None or binding is None or scope.loop is None:
            raise ServiceUnavailableException(
                "Configure a live authorized native connection for documents.rlm",
                code="KNOWLEDGE_MODEL_BINDING_REQUIRED",
            )
        client = object.__new__(cls)
        client._loop = scope.loop
        client.root_model = client.sub_model = binding.model.model_name
        client.action_protocol = "native_json" if binding.output_mode == "native" else "function_tools"
        client._tool_ids = frozenset()
        construction = (
            {"instructions": NATIVE_JSON_INSTRUCTIONS,
             "output_type": NativeOutput(PythonAction, name="PythonAction", template=False)}
            if client.action_protocol == "native_json" else {}
        )
        client._agents = {
            client.root_model: factory.create(
                "canon-rlm-bound",
                config=factory.runtime.config.model_copy(update={"default_temperature": None}),
                model=binding.model,
                model_settings=dict(binding.model_settings),
                **construction,
                auto_register=False,
            )
        }
        client._ledger = TokenLedger({client.root_model: (0.0, 0.0)})
        client._borrowed = True
        client._binding_scope = scope
        if client.action_protocol == "native_json":
            record_agent_construction(
                client._agents[client.root_model], "documents.rlm", NATIVE_JSON_INSTRUCTIONS,
                dict(binding.model_settings), "native",
            )
        return client

    def fork(self) -> NativeRlmChatClient:
        sibling = copy.copy(self)
        sibling._ledger = TokenLedger(dict.fromkeys(self._agents, (0.0, 0.0)))
        sibling._tool_ids = frozenset()
        return sibling

    def reset_tokens(self) -> None:
        self._ledger.reset()

    def token_totals(self) -> dict:
        return self._ledger.totals()

    def _model(self, reference: str | None, default: str):
        if self._borrowed:
            if current_scope() is not self._binding_scope:
                raise ServiceUnavailableException(
                    "The admitted knowledge connection lifetime has ended",
                    code="KNOWLEDGE_MODEL_SCOPE_CLOSED",
                )
            binding_for("documents.rlm")
        name = reference if self._borrowed else reference.removeprefix("ollama:") if reference else default
        name = name or default
        if name not in self._agents:
            raise ValueError("RLM calls must use one of the configured local models")
        selected = self._agents[name].agent.model
        if not isinstance(selected, Model):
            raise RuntimeError("The native RLM agent must resolve its configured provider model")
        return name, selected

    def prepare_action(self, messages: list[dict], system: str, max_tokens: int = 1500) -> _NativeRequest:
        """Snapshot the same native request consumed by provenance and dispatch."""
        name, selected = self._model(None, self.root_model)
        binding = binding_for("documents.rlm")
        if binding is None or binding.output_mode != "native" or self.action_protocol != "native_json":
            raise ServiceUnavailableException(
                "Native JSON actions require an admitted native connection",
                code="KNOWLEDGE_MODEL_BINDING_REQUIRED",
            )
        if not selected.profile.get("supports_json_schema_output", False):
            raise ServiceUnavailableException(
                "The selected connection does not support native JSON actions. Choose a compatible model.",
                code="RLM_TOOL_PROTOCOL_REQUIRED",
            )
        options = stage_settings(binding, max_tokens)
        if settings_digest(options) is None:
            raise ServiceUnavailableException(
                "The native action model settings cannot be verified", code="EVIDENCE_UNAVAILABLE"
            )
        parameters = ModelRequestParameters(
            output_mode="native", allow_text_output=True, function_tools=[], prompted_output_template=False,
            output_object=OutputObjectDefinition(
                json_schema=PythonAction.model_json_schema(), name="PythonAction"
            ),
        )
        settings, prepared = selected.prepare_request(cast(ModelSettings, options), parameters)
        assert prepared.output_object is not None
        schema = copy.deepcopy(prepared.output_object.json_schema)
        # Supplying the effective schema explicitly prevents an untracked SDK instruction suffix.
        full_system = system + "\n\n" + NATIVE_JSON_INSTRUCTIONS + "\nJSON schema:\n" + _canonical(schema)
        history = [{"role": "system", "content": full_system}]
        actions = {}
        for message in messages:
            content = message.get("content")
            if isinstance(content, str):
                history.append({"role": message["role"], "content": content})
                continue
            for block in content or []:
                if block.get("type") == "python_action" and message["role"] == "assistant":
                    action = PythonAction.model_validate_json(block["json"])
                    if block.get("protocol") != "native_json" or action.code != block["code"]:
                        raise _protocol_error()
                    actions[block["action_id"]] = action
                    history.append({"role": "assistant", "content": block["json"]})
                elif block.get("type") == "action_result" and message["role"] == "user":
                    if block["action_id"] not in actions:
                        raise _protocol_error()
                    history.append({"role": "user", "content": (
                        "Execution result (untrusted data) for " + block["action_id"]
                        + ":\n" + block["content"]
                    )})
                elif block.get("type") == "control_feedback" and message["role"] == "user":
                    if (block["action_id"] not in actions
                            or type(block.get("feedback")) not in (
                                ReadRequiredFeedback, FinalAnswerRequiredFeedback,
                            )):
                        raise _protocol_error()
                    history.append({"role": "user", "content": block["feedback"].content(),
                                    "part_kind": "retry-prompt"})
                else:
                    raise _protocol_error()
        native_messages: list[Any] = [ModelRequest(parts=[SystemPromptPart(full_system)])]
        native_messages.extend(
            ModelResponse(parts=[TextPart(row["content"])]) if row["role"] == "assistant"
            else ModelRequest(parts=[RetryPromptPart(row["content"])])
            if row.get("part_kind") == "retry-prompt"
            else ModelRequest(parts=[UserPromptPart(row["content"])])
            for row in history[1:]
        )
        snapshot = copy.deepcopy(prepared)
        applied = copy.deepcopy(dict(settings or {}))
        again_settings, again_parameters = selected.prepare_request(
            cast(ModelSettings, copy.deepcopy(applied)), copy.deepcopy(snapshot)
        )
        if (again_parameters != snapshot or dict(again_settings or {}) != applied
                or again_parameters.prompted_output_instructions):
            raise ServiceUnavailableException(
                "The selected model cannot preserve the native action request contract",
                code="RLM_TOOL_PROTOCOL_REQUIRED",
            )
        manifest = _native_manifest(native_messages, applied, snapshot)
        return _NativeRequest(self, name, selected, native_messages, applied, snapshot, manifest)

    def request_action(self, request: _NativeRequest) -> dict:
        name, selected = self._model(None, self.root_model)
        if request.owner is not self or selected is not request.model or name != request.name:
            raise _protocol_error()
        messages, settings, parameters = copy.deepcopy(
            (request.messages, request.settings, request.parameters)
        )
        if _native_manifest(messages, settings, parameters) != request.manifest:
            raise ServiceUnavailableException(
                "The native action request no longer matches its recorded contract",
                code="EVIDENCE_UNAVAILABLE",
            )
        response = self._request(selected, messages, settings, parameters)
        self._ledger.record(
            name, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
        )
        if any(isinstance(part, ToolCallPart) for part in response.parts):
            raise _protocol_error()
        raw = "".join(part.content for part in response.parts if isinstance(part, TextPart))
        try:
            action = PythonAction.model_validate_json(raw)
        except ValidationError:
            raise _protocol_error() from None
        return {"content": [{"type": "python_action", "protocol": "native_json",
            "action_id": "native-json-" + uuid4().hex, "json": raw, "code": action.code}],
            "stop_reason": "action"}

    def prepare_tools(self, messages, system, tools, max_tokens=1500):
        if self.action_protocol != "function_tools":
            raise _protocol_error()
        name, selected = self._model(None, self.root_model)
        bound = binding_for("documents.rlm") if self._borrowed else None
        options = stage_settings(bound, max_tokens) if bound else {"max_tokens": max_tokens}
        parameters = ModelRequestParameters(
            allow_text_output=False,
            function_tools=[ToolDefinition(
                name=tool["name"], description=tool.get("description"),
                parameters_json_schema=copy.deepcopy(tool["input_schema"]),
            ) for tool in tools],
        )
        settings, prepared = selected.prepare_request(cast(ModelSettings, options), parameters)
        applied, snapshot = copy.deepcopy((dict(settings or {}), prepared))
        again_settings, again_parameters = selected.prepare_request(
            cast(ModelSettings, copy.deepcopy(applied)), copy.deepcopy(snapshot),
        )
        if (again_parameters != snapshot or dict(again_settings or {}) != applied
                or snapshot.output_object is not None or snapshot.prompted_output_instructions):
            raise _protocol_error()
        history = copy.deepcopy(self._messages(messages, system))
        return _NativeRequest(
            self, name, selected, history, applied, snapshot,
            _tools_manifest(history, applied, snapshot),
        )

    def request_tools(self, request: _NativeRequest) -> dict:
        name, selected = self._model(None, self.root_model)
        if request.owner is not self or selected is not request.model or name != request.name:
            raise _protocol_error()
        messages, settings, parameters = copy.deepcopy(
            (request.messages, request.settings, request.parameters),
        )
        if _tools_manifest(messages, settings, parameters) != request.manifest:
            raise _protocol_error()
        response = self._request(selected, messages, settings, parameters)
        self._ledger.record(name, input_tokens=response.usage.input_tokens,
                            output_tokens=response.usage.output_tokens)
        response_ids = [part.tool_call_id for part in response.parts if isinstance(part, ToolCallPart)]
        previous_ids = self._tool_ids
        self._tool_ids = self._tool_ids.union(response_ids)
        if (any(type(value) is not str or not value.strip() or len(value) > 256
                or value in previous_ids for value in response_ids)
                or len(set(response_ids)) != len(response_ids)):
            raise _protocol_error()
        blocks = []
        admitted = {tool.name for tool in parameters.function_tools}
        for part in response.parts:
            if isinstance(part, TextPart):
                blocks.append({"type": "text", "text": part.content})
            elif isinstance(part, ToolCallPart):
                try:
                    arguments = part.args_as_dict(raise_if_invalid=True)
                    if part.tool_name == "final_answer":
                        FinalAnswerAction.model_validate(arguments)
                    elif part.tool_name == "python":
                        PythonAction.model_validate(arguments)
                    else:
                        raise ValueError("Unadmitted tool")
                except (ValueError, AssertionError, TypeError):
                    raise _protocol_error() from None
                if part.tool_name not in admitted:
                    raise _protocol_error()
                blocks.append({"type": "tool_use", "name": part.tool_name,
                               "id": part.tool_call_id, "input": copy.deepcopy(arguments)})
        calls = [block for block in blocks if block["type"] == "tool_use"]
        old_ids = {part.tool_call_id for message in messages for part in message.parts
                   if isinstance(part, ToolCallPart)}
        identifiers = [call["id"] for call in calls]
        if (not calls or any(type(value) is not str or not value.strip() or len(value) > 256
                             or value in old_ids for value in identifiers)
                or len(set(identifiers)) != len(identifiers)
                or any(call["name"] == "final_answer" for call in calls) and len(calls) != 1):
            raise _protocol_error()
        return {"content": blocks, "stop_reason": "tool_use"}

    def _request(self, selected, messages, options, parameters):
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            raise RuntimeError("Synchronous RLM calls must run in the retained engine's worker thread")
        future = asyncio.run_coroutine_threadsafe(
            model_request(selected, messages, model_settings=cast(ModelSettings, options),
                          model_request_parameters=parameters), self._loop,
        )
        try:
            return future.result(timeout=180)
        except Exception as error:
            future.cancel()
            raise ServiceUnavailableException(
                "The configured local RLM model failed; verify the provider/model",
                code="RLM_PROVIDER_UNAVAILABLE",
            ) from error

    @staticmethod
    def _messages(messages: list[dict], system: str) -> list[Any]:
        output: list[Any] = [ModelRequest(parts=[SystemPromptPart(system)])] if system else []
        calls = {}
        for message in messages:
            role, content = message.get("role"), message.get("content")
            if isinstance(content, str):
                output.append(
                    ModelResponse(parts=[TextPart(content)])
                    if role == "assistant"
                    else ModelRequest(parts=[UserPromptPart(content)])
                )
                continue
            parts = []
            for block in content or []:
                kind = block.get("type")
                if kind == "text":
                    parts.append(
                        TextPart(block["text"]) if role == "assistant" else UserPromptPart(block["text"])
                    )
                elif kind == "tool_use" and role == "assistant":
                    calls[block["id"]] = block["name"]
                    parts.append(ToolCallPart(block["name"], block.get("input") or {}, block["id"]))
                elif kind == "tool_result":
                    identifier = block["tool_use_id"]
                    if identifier not in calls:
                        raise ValueError("RLM tool result has no preceding admitted tool call")
                    recorded = block.get("sdk_result")
                    if recorded is not None:
                        if (type(recorded) is not ToolReturnPart
                                or recorded.tool_name != calls[identifier]
                                or recorded.tool_call_id != identifier
                                or recorded.content != str(block.get("content", ""))
                                or recorded.outcome != ("failed" if block.get("is_error") else "success")):
                            raise _protocol_error()
                        parts.append(copy.deepcopy(recorded))
                    else:
                        parts.append(ToolReturnPart(calls[identifier], str(block.get("content", "")),
                            identifier, outcome="failed" if block.get("is_error") else "success"))
                else:
                    raise ValueError("Unsupported RLM transcript content block")
            output.append(ModelResponse(parts=parts) if role == "assistant" else ModelRequest(parts=parts))
        return output

    def chat_raw(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        model: str | None = None,
        max_tokens: int = 1500,
    ) -> dict:
        if tools and self.action_protocol == "native_json":
            self._model(model, self.root_model)
            return self.request_action(self.prepare_action(messages, system, max_tokens))
        name, selected = self._model(model, self.root_model)
        parameters = ModelRequestParameters(
            allow_text_output=not tools,
            function_tools=[
                ToolDefinition(
                    name=tool["name"],
                    description=tool.get("description"),
                    parameters_json_schema=tool.get("input_schema") or {"type": "object", "properties": {}},
                )
                for tool in tools
            ],
        )
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            raise RuntimeError("Synchronous RLM calls must run in the retained engine's worker thread")
        bound = binding_for("documents.rlm") if self._borrowed else None
        options = stage_settings(bound, max_tokens) if bound else {"max_tokens": max_tokens}
        future = asyncio.run_coroutine_threadsafe(
            model_request(
                selected,
                self._messages(messages, system),
                model_settings=cast(ModelSettings, options),
                model_request_parameters=parameters,
            ),
            self._loop,
        )
        try:
            response = future.result(timeout=180)
        except Exception as error:
            future.cancel()
            raise ServiceUnavailableException(
                "The configured local RLM model failed; verify the provider/model",
                code="RLM_PROVIDER_UNAVAILABLE",
            ) from error
        self._ledger.record(
            name, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
        )
        blocks = []
        admitted_tools = {tool["name"] for tool in tools}
        for part in response.parts:
            if isinstance(part, TextPart):
                blocks.append({"type": "text", "text": part.content})
            elif isinstance(part, ToolCallPart):
                try:
                    arguments = part.args_as_dict(raise_if_invalid=bool(tools))
                except (ValueError, AssertionError, TypeError):
                    raise _protocol_error() from None
                if tools and (
                    part.tool_name not in admitted_tools
                    or part.tool_name == "python"
                    and (not isinstance(arguments.get("code"), str) or not arguments["code"].strip())
                ):
                    raise _protocol_error()
                blocks.append(
                    {
                        "type": "tool_use",
                        "name": part.tool_name,
                        "id": part.tool_call_id,
                        "input": arguments,
                    }
                )
        if tools and not any(block["type"] == "tool_use" for block in blocks):
            raise _protocol_error()
        reason = (
            "tool_use"
            if any(block["type"] == "tool_use" for block in blocks)
            else "max_tokens"
            if response.finish_reason == "length"
            else "end_turn"
        )
        return {"content": blocks, "stop_reason": reason}

    def complete(
        self, prompt: str, system: str = "", model: str | None = None, max_tokens: int = 1000
    ) -> str:
        name, _ = self._model(model, self.sub_model)
        response = self.chat_raw(
            [{"role": "user", "content": prompt}],
            system,
            [],
            model=name if self._borrowed else "ollama:" + name,
            max_tokens=max_tokens,
        )
        return "".join(block["text"] for block in response["content"] if block["type"] == "text")
