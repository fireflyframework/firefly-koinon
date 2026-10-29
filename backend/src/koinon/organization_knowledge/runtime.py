# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A bounded operation borrows its admitted policy without extending its lifetime."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING

from pydantic import ValidationError
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot

if TYPE_CHECKING:
    from koinon.organization_knowledge.service import OrganizationKnowledgeService


@dataclass(frozen=True, slots=True)
class _Scope:
    snapshot: OrganizationKnowledgeSnapshot
    subject: str
    closed: Event
    parent: "_Scope | None"

    def check(self):
        current: _Scope | None = self
        while current is not None:
            if current.closed.is_set():
                raise AccessDenied(
                    "The admitted knowledge policy is no longer active", code="KNOWLEDGE_POLICY_CLOSED"
                )
            current = current.parent


_current: ContextVar[_Scope | None] = ContextVar("koinon_knowledge_policy", default=None)


def _checked(value) -> OrganizationKnowledgeSnapshot:
    raw = value.model_dump(mode="json") if isinstance(value, OrganizationKnowledgeSnapshot) else value
    return OrganizationKnowledgeSnapshot.model_validate(raw)


def current_snapshot(subject: str, tenant_id: str) -> OrganizationKnowledgeSnapshot | None:
    scope = _current.get()
    if scope is None:
        return None
    scope.check()
    if scope.subject != subject or scope.snapshot.tenant_id != tenant_id:
        raise AccessDenied("The knowledge policy belongs to another operation", code="KNOWLEDGE_POLICY_SCOPE")
    return scope.snapshot


@contextmanager
def bind_snapshot(value: OrganizationKnowledgeSnapshot, subject: str):
    value = _checked(value)
    if not isinstance(subject, str) or not 0 < len(subject) <= 512:
        raise AccessDenied("A current subject is required", code="KNOWLEDGE_POLICY_SCOPE")
    previous = current_snapshot(subject, value.tenant_id)
    if previous is not None and previous.digest != value.digest:
        raise AccessDenied("The admitted knowledge policy cannot be replaced", code="KNOWLEDGE_POLICY_SCOPE")
    scope = _Scope(value, subject, Event(), _current.get())
    token = _current.set(scope)
    try:
        yield value
    finally:
        scope.closed.set()
        _current.reset(token)


async def settings_for_operation(
    service: "OrganizationKnowledgeService | None", subject: str, tenant_id: str
) -> OrganizationKnowledgeSnapshot:
    value = current_snapshot(subject, tenant_id)
    if value is not None:
        return value
    if service is None:
        raise ServiceUnavailableException(
            "Organization knowledge settings are unavailable", code="KNOWLEDGE_SETTINGS_UNAVAILABLE"
        )
    return await service.snapshot(subject, tenant_id)


def snapshot_for_run(run) -> OrganizationKnowledgeSnapshot | None:
    raw = getattr(run, "knowledge_settings_snapshot", None)
    if raw is None:
        return None
    try:
        value = _checked(raw)
        if value.tenant_id != run.tenant_id:
            raise ValueError("Tenant differs")
        return value
    except (ValidationError, ValueError, TypeError):
        raise ConflictException(
            "The answer's recorded knowledge settings cannot be verified. Start a new answer.",
            code="KNOWLEDGE_SETTINGS_SNAPSHOT_INVALID",
        ) from None
