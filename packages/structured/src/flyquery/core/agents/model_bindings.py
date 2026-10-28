# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Borrowed request-local native connections; callers own their public lifetimes."""

from __future__ import annotations

from asyncio import AbstractEventLoop, get_running_loop
from collections.abc import Mapping
from contextvars import ContextVar, Token
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Literal

from pydantic_ai.models import Model
from pyfly.agentic.embeddings import BaseEmbedder
from pyfly.kernel import ServiceUnavailableException

from flyquery.core.agents.provenance import AgentConstruction, ModelBindingProvenance, settings_digest
from flyquery.web.conventions.context import current_tenant_context


@dataclass(frozen=True)
class ModelBinding:
    model: Model
    model_settings: Mapping[str, Any]
    provider: str
    api: Literal["chat", "responses", "messages"]
    output_mode: Literal["native", "default"] = "default"
    provenance: ModelBindingProvenance | None = None

    def __post_init__(self):
        if not isinstance(self.model, Model):
            raise TypeError("A binding must borrow an already resolved native Model")
        if self.api not in {"chat", "responses", "messages"} or self.output_mode not in {"native", "default"}:
            raise ValueError("Unsupported native connection capability")
        object.__setattr__(self, "model_settings", MappingProxyType(deepcopy(dict(self.model_settings))))


@dataclass(frozen=True)
class EmbeddingBinding:
    embedder: BaseEmbedder
    embedding_model: str
    dimensions: int
    storage_dimensions: int
    space_id: str
    versioned: bool = False


@dataclass
class BindingScope:
    tenant_id: str
    workspace_id: str
    subject: str
    bindings: Mapping[str, ModelBinding]
    embeddings: Mapping[str, EmbeddingBinding]
    required: bool
    loop: AbstractEventLoop | None
    closed: bool = False
    agents: dict[int, tuple[Any, AgentConstruction]] = field(default_factory=dict)


@dataclass(frozen=True)
class BindingToken:
    token: Token
    scope: BindingScope


_current: ContextVar[BindingScope | None] = ContextVar("flyquery_model_bindings", default=None)


def push_bindings(
    *,
    tenant_id: str,
    workspace_id: str,
    subject: str,
    bindings: Mapping[str, ModelBinding],
    required: bool = True,
    embeddings: Mapping[str, EmbeddingBinding] | None = None,
) -> BindingToken:
    try:
        loop = get_running_loop()
    except RuntimeError:
        loop = None
    scope = BindingScope(
        tenant_id,
        str(workspace_id),
        subject,
        MappingProxyType(dict(bindings)),
        MappingProxyType(dict(embeddings or {})),
        required,
        loop,
    )
    return BindingToken(_current.set(scope), scope)


def reset_bindings(token: BindingToken) -> None:
    _current.reset(token.token)
    token.scope.closed = True
    token.scope.agents.clear()


def current_scope() -> BindingScope | None:
    scope = _current.get()
    if scope is None:
        return None
    if scope.closed:
        raise ServiceUnavailableException(
            "Knowledge connection lifetime has ended", code="KNOWLEDGE_MODEL_SCOPE_CLOSED"
        )
    context = current_tenant_context()
    if context is None or (context.tenant_id, str(context.workspace_id), context.actor) != (
        scope.tenant_id,
        scope.workspace_id,
        scope.subject,
    ):
        raise ServiceUnavailableException(
            "Knowledge connection does not match the verified tenant, workspace and subject",
            code="KNOWLEDGE_MODEL_SCOPE_MISMATCH",
        )
    return scope


def binding_for(role: str | None) -> ModelBinding | None:
    scope = current_scope()
    if scope is None:
        return None
    binding = scope.bindings.get(role) if role else None
    if binding is None and scope.required:
        raise ServiceUnavailableException(
            f"Configure an authorized native connection for knowledge role {role or 'unknown'}",
            code="KNOWLEDGE_MODEL_BINDING_REQUIRED",
        )
    return binding


def embedding_for(role: str) -> EmbeddingBinding | None:
    scope = current_scope()
    if scope is None:
        return None
    binding = scope.embeddings.get(role)
    if binding is None and scope.required:
        raise ServiceUnavailableException(
            f"Configure an authorized embedding connection and compatible indexed space for {role}",
            code="KNOWLEDGE_EMBEDDING_BINDING_REQUIRED",
        )
    return binding


def stage_settings(binding: ModelBinding, limit: int) -> dict[str, Any]:
    selected = deepcopy(dict(binding.model_settings))
    requested = selected.get("max_tokens") or limit
    if requested > limit and any(
        word in key.lower() for key in selected for word in ("thinking", "reasoning", "budget")
    ):
        raise ServiceUnavailableException(
            "The selected reasoning options exceed this knowledge stage's output budget; "
            "configure a compatible role",
            code="KNOWLEDGE_MODEL_BUDGET_INCOMPATIBLE",
        )
    selected["max_tokens"] = min(requested, limit)
    return selected


def record_agent_construction(agent, role, instructions, model_settings, output_mode):
    scope = current_scope()
    if scope is None:
        return
    binding = binding_for(role)
    if binding is None:
        return
    scope.agents[id(agent)] = (
        agent,
        AgentConstruction(
            role=role,
            provenance=binding.provenance,
            provider=binding.provider,
            model_name=binding.model.model_name,
            model_class=type(binding.model).__module__ + "." + type(binding.model).__qualname__,
            api=binding.api,
            output_mode=output_mode,
            instructions_sha256=sha256(instructions.encode()).hexdigest(),
            applied_model_settings_sha256=settings_digest(model_settings),
        ),
    )


def agent_construction(agent) -> AgentConstruction | None:
    scope = current_scope()
    if scope is None:
        return None
    value = scope.agents.get(id(agent))
    return value[1] if value is not None and value[0] is agent else None


def model_reference(role: str, standalone: str) -> str:
    binding = binding_for(role)
    return f"{binding.provider}:{binding.model.model_name}" if binding else standalone
