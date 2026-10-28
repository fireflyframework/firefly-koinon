# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native application-owned local models behind the retained CodeAct protocol."""

from __future__ import annotations

import asyncio
import copy
from typing import Any, cast

from pydantic_ai.direct import model_request
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition
from pyfly.agentic.factory import AgentFactory
from pyfly.kernel import ServiceUnavailableException

from flycanon.config import CanonSettings
from flycanon.core.agents.model_bindings import binding_for, current_scope, stage_settings
from flycanon.core.services.query.rlm.chat import TokenLedger


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
        client._agents = {
            client.root_model: factory.create(
                "canon-rlm-bound",
                config=factory.runtime.config.model_copy(update={"default_temperature": None}),
                model=binding.model,
                model_settings=dict(binding.model_settings),
                auto_register=False,
            )
        }
        client._ledger = TokenLedger({client.root_model: (0.0, 0.0)})
        client._borrowed = True
        return client

    def fork(self) -> NativeRlmChatClient:
        sibling = copy.copy(self)
        sibling._ledger = TokenLedger(dict.fromkeys(self._agents, (0.0, 0.0)))
        return sibling

    def reset_tokens(self) -> None:
        self._ledger.reset()

    def token_totals(self) -> dict:
        return self._ledger.totals()

    def _model(self, reference: str | None, default: str):
        if self._borrowed:
            binding_for("documents.rlm")
        name = reference if self._borrowed else reference.removeprefix("ollama:") if reference else default
        name = name or default
        if name not in self._agents:
            raise ValueError("RLM calls must use one of the configured local models")
        selected = self._agents[name].agent.model
        if not isinstance(selected, Model):
            raise RuntimeError("The native RLM agent must resolve its configured provider model")
        return name, selected

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
                    parts.append(
                        ToolReturnPart(
                            calls[identifier],
                            str(block.get("content", "")),
                            identifier,
                            outcome="failed" if block.get("is_error") else "success",
                        )
                    )
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
        for part in response.parts:
            if isinstance(part, TextPart):
                blocks.append({"type": "text", "text": part.content})
            elif isinstance(part, ToolCallPart):
                blocks.append(
                    {
                        "type": "tool_use",
                        "name": part.tool_name,
                        "id": part.tool_call_id,
                        "input": part.args_as_dict(),
                    }
                )
        if tools and not any(block["type"] == "tool_use" for block in blocks):
            raise ServiceUnavailableException(
                "The configured local RLM model did not use the required evidence tool; "
                "select a model with reliable tool calling or use the retrieval answer mode",
                code="RLM_TOOL_PROTOCOL_REQUIRED",
            )
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
