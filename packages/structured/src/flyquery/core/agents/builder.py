# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Centralised :class:`FireflyAgent` constructor.

Every stage that talks to an LLM (consolidation, RAG answer) goes
through :func:`build_agent`. The helper folds the operator-tunable
output-token budget into ``model_settings`` and keeps the
construction recipe identical across stages so a tuning change
lands in one place.

Background -- why ``max_tokens`` matters
========================================
Anthropic's API defaults to ``max_tokens=4096`` and OpenAI clamps
similarly. For structured outputs (pydantic-ai's ``output_type=...``
contract -- a JSON envelope the model must produce in one shot) the
4096 ceiling truncates the response mid-array on dense business
documents. pydantic-ai then retries; when retries also overflow,
the parsed output ends up empty (``candidates=[]``) and the user
sees a silent zero-result. Bumping to ``max_tokens=8192`` (Sonnet
4.6's public ceiling) stops the silent-truncation tail; operators
on models with a higher ceiling can raise the env var further.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import NativeOutput
from pyfly.kernel import ServiceUnavailableException

from flyquery.config import FlyquerySettings
from flyquery.core.agents.model_bindings import (
    binding_for,
    current_scope,
    record_agent_construction,
    stage_settings,
)
from flyquery.core.observability import build_agent_middleware

_ROLES = {
    "flyquery-grounding": "structured.grounding",
    "flyquery-generation": "structured.generation",
    "flyquery-critic": "structured.critic",
    "flyquery-explainer": "structured.explainer",
    "flyquery-describe": "structured.describe",
    "flyquery-column-name-proposer": "structured.describe",
    "flyquery-relation-proposer": "structured.relation_proposal",
    "flyquery-rename-detector": "structured.rename_detection",
}


def build_agent(
    *,
    name: str,
    model: str,
    output_type: type,
    instructions: str,
    settings: FlyquerySettings,
    max_output_tokens: int | None = None,
    extra_settings: dict[str, Any] | None = None,
) -> Any:
    """Construct a :class:`FireflyAgent` with the standard knobs.

    Args:
        name: Identifier passed to ``FireflyAgent`` -- shows up in
            tracing + metrics. Use a stable kebab/snake-cased value
            (``flyquery-consolidator``, ``flyquery-answerer``).
        model: Provider:model id (e.g. ``anthropic:claude-sonnet-4-6``).
        output_type: pydantic model the agent's structured output is
            validated against. The agent's ``run()`` returns an
            instance of this type.
        instructions: Rendered system prompt.
        settings: :class:`FlyquerySettings` instance the agent reads
            cross-cutting knobs from. Required so the helper has
            access to the configured output-token budget without
            requiring callers to plumb the env var themselves.
        max_output_tokens: Optional override for this specific call.
            ``None`` falls back to ``settings.agent_max_output_tokens``.
        extra_settings: Optional extra ``model_settings`` entries.
            Caller-provided keys WIN on conflict so a stage can cap
            below the global budget (e.g. a 1-token classifier).

    The agent is constructed with ``auto_register=False`` because
    each stage builds a fresh agent per call. Auto-registering would
    raise duplicate-name errors when the same stage is exercised by
    sync + async paths in the same process.
    """
    if getattr(settings, "_require_model_bindings", False):
        scope = current_scope()
        if scope is None or not scope.required:
            raise ServiceUnavailableException(
                "Select an authorized request-local knowledge model connection",
                code="KNOWLEDGE_MODEL_BINDING_REQUIRED",
            )

    factory = settings._agent_factory
    if factory is None:
        raise RuntimeError("Bind the ApplicationContext-owned AgentFactory before building structured agents")

    resolved_max = resolve_max_output_tokens(settings, override=max_output_tokens)
    role = _ROLES.get(name)
    binding = binding_for(role)
    model_settings: dict[str, Any] = {"max_tokens": resolved_max}
    if extra_settings:
        # Caller-provided settings win on conflict -- a stage can cap
        # itself below the default by passing ``max_tokens=128`` in
        # ``extra_settings``.
        model_settings.update(extra_settings)
    if binding:
        model_settings = stage_settings(binding, resolved_max)

    connection_config = (
        {"config": factory.runtime.config.model_copy(update={"default_temperature": None})} if binding else {}
    )
    agent = factory.create(
        name,
        **connection_config,
        model=binding.model if binding else model,
        instructions=instructions,
        output_type=NativeOutput(output_type)
        if output_type is not str
        and (
            binding.output_mode == "native"
            if binding
            else isinstance(model, str) and model.startswith("ollama:")
        )
        else output_type,
        model_settings=model_settings,
        middleware=build_agent_middleware(),
        auto_register=False,
    )
    if binding is not None:
        record_agent_construction(
            agent,
            role,
            instructions,
            model_settings,
            "text" if output_type is str else binding.output_mode,
        )
    return agent


def resolve_max_output_tokens(
    settings: FlyquerySettings,
    *,
    override: int | None = None,
) -> int:
    """Return the effective ``max_tokens`` value for an agent call.

    Resolution order (first non-None wins):

    1. ``override`` -- the caller's explicit per-call ceiling.
    2. ``settings.agent_max_output_tokens`` -- the global default.

    The per-stage env-var overrides (``consolidator_max_output_tokens``,
    ``answer_max_output_tokens``) are NOT consulted here -- callers
    pass them explicitly via ``override`` so the resolution stays
    one-way and predictable. This avoids the resolver guessing which
    stage is asking.
    """
    if override is not None:
        return override
    return settings.agent_max_output_tokens
