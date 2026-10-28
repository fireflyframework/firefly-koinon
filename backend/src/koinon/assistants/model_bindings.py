# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Borrow a native model only within an authorized run and its resource lifetime."""

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from pydantic_ai.models import Model
from pyfly.kernel import ServiceUnavailableException


@dataclass(frozen=True)
class BorrowedModel:
    model: Model
    model_settings: Mapping[str, Any]
    provider: str
    api: Literal["chat", "responses", "messages"]
    output_mode: Literal["native", "default"] = "default"
    agent_id: str | None = None
    agent_revision: int | None = None
    provider_id: str | None = None
    provider_revision: int | None = None
    model_id: str | None = None
    options_sha256: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "model_settings", MappingProxyType(deepcopy(dict(self.model_settings))))


@dataclass
class _Scope:
    tenant_id: str
    subject: str
    binding: BorrowedModel
    active: bool = True


_CURRENT: ContextVar[_Scope | None] = ContextVar("koinon_borrowed_model", default=None)


@contextmanager
def bind_model(tenant_id: str, subject: str, binding: BorrowedModel):
    scope = _Scope(tenant_id, subject, binding)
    token = _CURRENT.set(scope)
    try:
        yield binding
    finally:
        scope.active = False
        _CURRENT.reset(token)


def current_model_binding(tenant_id: str, subject: str) -> BorrowedModel | None:
    scope = _CURRENT.get()
    if scope is None:
        return None
    if not scope.active or scope.tenant_id != tenant_id or scope.subject != subject:
        raise ServiceUnavailableException(
            "The authorized model binding is unavailable in this scope", code="MODEL_BINDING_UNAVAILABLE"
        )
    return scope.binding
