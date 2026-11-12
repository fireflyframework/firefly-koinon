# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private exact-version admission while one task holds a local policy snapshot."""

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from pyfly.data.transaction import current_unit_of_work
from pyfly.data.transaction.unit_of_work import UnitOfWork

from koinon.integrations.content_sources.errors import SourceError
from koinon.security.authority import PRIMARY_POLICY_UNIT


@dataclass(frozen=True, slots=True)
class CuratedIdentity:
    item_id: str
    native_workspace_id: str
    native_item_id: str
    version_id: str
    version: int
    canonical_workspace_id: str


@dataclass(slots=True)
class _Capability:
    actor: str
    tenant: str
    task: object
    identities: tuple[CuratedIdentity, ...]
    unit: UnitOfWork
    active: bool = True


_current: ContextVar[_Capability | None] = ContextVar("source_curated_read_capability", default=None)


@contextmanager
def curated_capability(actor, tenant, identities):
    if _current.get() is not None:
        raise SourceError("authority_changed")
    unit = current_unit_of_work("primary")
    if unit is None or unit.completed or not unit.read_only or unit.definition.name != PRIMARY_POLICY_UNIT:
        raise SourceError("authority_changed")
    capability = _Capability(actor, tenant, asyncio.current_task(), tuple(identities), unit)
    token = _current.set(capability)
    try:
        yield
    finally:
        capability.active = False
        _current.reset(token)


def curated_identity(actor, tenant, item, version=None):
    capability = _current.get()
    if capability is None:
        return None
    if (
        not capability.active
        or capability.task is not asyncio.current_task()
        or (capability.actor, capability.tenant) != (actor, tenant)
        or current_unit_of_work("primary") is not capability.unit
        or capability.unit.completed
        or not capability.unit.read_only
        or capability.unit.definition.name != PRIMARY_POLICY_UNIT
    ):
        raise SourceError("authority_changed")
    selected = tuple(
        identity
        for identity in capability.identities
        if identity.item_id == item and (version is None or identity.version == version)
    )
    if len(selected) != 1:
        raise SourceError("authority_changed")
    return selected[0]
