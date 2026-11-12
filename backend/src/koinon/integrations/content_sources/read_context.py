# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Request-owned reader choices; values are preferences, never permission evidence."""

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_dtos import (
    ReaderSelectionSnapshot,
    ReaderSourceSelection,
    validate_selections,
)


@dataclass
class _Choices:
    actor: str
    tenant: str
    values: tuple[ReaderSourceSelection, ...] | None
    task: object
    active: bool = True


_choices: ContextVar[_Choices | None] = ContextVar("source_reader_choices", default=None)


@dataclass
class _QueuedSelection:
    actor: str
    tenant: str
    snapshot: ReaderSelectionSnapshot
    task: object
    active: bool = True


_queued: ContextVar[_QueuedSelection | None] = ContextVar("queued_source_reader_baseline", default=None)


@contextmanager
def reader_source_snapshot(actor, tenant, snapshot):
    """Private request intent, bound to this task/lifetime; never a remote grant."""
    validate_selections(snapshot.connections)
    value = _QueuedSelection(actor, tenant, snapshot, asyncio.current_task())
    token = _queued.set(value)
    try:
        yield
    finally:
        value.active = False
        _queued.reset(token)


def current_reader_snapshot(actor, tenant, overrides):
    value = _queued.get()
    if value is None:
        return None
    if (
        not value.active
        or value.task is not asyncio.current_task()
        or (value.actor, value.tenant) != (actor, tenant)
    ):
        raise SourceError("authority_changed")
    if overrides is not None and set(overrides) != set(value.snapshot.connections):
        raise SourceError("authority_changed")
    return value.snapshot


@contextmanager
def reader_source_scope(actor, tenant, connections):
    values = (
        None
        if connections is None
        else tuple(ReaderSourceSelection.model_validate(value) for value in connections)
    )
    if values is not None:
        validate_selections(values)
    selection = _Choices(actor, tenant, values, asyncio.current_task())
    token = _choices.set(selection)
    try:
        yield
    finally:
        selection.active = False
        _choices.reset(token)


def current_reader_choices(actor, tenant):
    selection = _choices.get()
    if selection is None:
        return None
    if (
        not selection.active
        or selection.task is not asyncio.current_task()
        or (selection.actor, selection.tenant) != (actor, tenant)
    ):
        raise SourceError("access_denied")
    return selection.values
