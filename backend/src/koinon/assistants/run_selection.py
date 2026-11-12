# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable queued request preferences; these values never grant source access."""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pyfly.kernel import InvalidRequestException, ServiceUnavailableException
from sqlalchemy import select

from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_dtos import (
    ReaderSelectionSnapshot,
    ReaderSourceSelection,
    validate_selections,
)
from koinon.integrations.content_sources.read_service import SourceReadOperation
from koinon.security.authority import primary_authority


def ordered(values):
    return tuple(
        sorted(values, key=lambda item: (item.provider, item.external_tenant or "", item.connection_id))
    )


class RunSourceSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: int = Field(default=1, strict=True, ge=1, le=1)
    mode: Literal["saved", "explicit", "local_only"]
    revision: int | None = Field(default=None, strict=True, ge=0)
    connections: tuple[ReaderSourceSelection, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def coherent(self):
        validate_selections(self.connections)
        if (
            self.mode == "saved"
            and self.revision is None
            or self.mode != "saved"
            and self.revision is not None
            or self.mode == "explicit"
            and not self.connections
            or self.mode == "local_only"
            and self.connections
        ):
            raise ValueError("Invalid queued source selection")
        # Match SQLAlchemy's default JSON serializer, including ASCII escapes and spaces.
        if len(json.dumps(self.model_dump(mode="json")).encode("utf-8")) > 131072:
            raise ValueError("Queued source selection is too large")
        return self

    def snapshot(self):
        return ReaderSelectionSnapshot(ordered(self.connections), self.revision)


def request_choices(values):
    raw = values.get("reader_source_connections")
    if raw is None:
        return None
    try:
        if not isinstance(raw, list):
            raise ValueError()
        choices = ordered(tuple(ReaderSourceSelection.model_validate(item) for item in raw))
        validate_selections(choices)
        return choices
    except (TypeError, ValueError) as error:
        raise InvalidRequestException(
            "Choose valid source accounts", code="INVALID_SOURCE_SELECTION"
        ) from error


def stored_selection(value):
    try:
        return (
            RunSourceSelection.model_validate(value)
            if value is not None
            else RunSourceSelection(
                mode="local_only",
                connections=(),
            )
        )
    except ValueError as error:
        raise SourceError("unavailable") from error


async def capture_selection(assistants, actor, tenant, choices):
    reader = assistants.source_reader.get() if assistants.source_reader is not None else None
    if reader is None:
        if choices:
            raise ServiceUnavailableException("Source accounts are unavailable", code="SOURCES_UNAVAILABLE")
        return RunSourceSelection(mode="local_only", connections=())
    snapshot = await reader.selections.resolve(actor, tenant, choices)
    async with primary_authority(fresh=True):
        await reader.selections.records.validate_owned(actor, tenant, snapshot.connections)
    try:
        return RunSourceSelection(
            mode="saved" if choices is None else "explicit" if choices else "local_only",
            revision=snapshot.revision,
            connections=ordered(snapshot.connections),
        )
    except ValueError as error:
        raise InvalidRequestException(
            "Source account selection exceeds the supported request size", code="INVALID_SOURCE_SELECTION"
        ) from error


async def confirm_selection(reader, actor, tenant, value, *, local=False):
    snapshot = value.snapshot()
    if value.mode == "saved":
        current = (
            await reader.selections.records.snapshot(tenant, actor)
            if local
            else await reader.selections.get(actor, tenant)
        )
        if current.revision != value.revision or ordered(current.connections) != snapshot.connections:
            raise SourceError("authority_changed")
    if local:
        await reader.selections.records.validate_owned(actor, tenant, snapshot.connections)
    else:
        async with primary_authority(fresh=True):
            await reader.selections.records.validate_owned(actor, tenant, snapshot.connections)


async def lock_selection(assistants, actor, tenant, value):
    reader = assistants.source_reader.get() if assistants.source_reader is not None else None
    if reader is None:
        if value.connections:
            raise SourceError("unavailable")
        return
    await reader.selections.lock_confirm(actor, tenant, value.snapshot())
    session = assistants.runs._require_session()
    await session.execute(
        select(PersonalSourceConnection.id)
        .where(PersonalSourceConnection.id.in_([item.connection_id for item in value.connections]))
        .order_by(PersonalSourceConnection.id)
        .with_for_update()
    )
    await confirm_selection(reader, actor, tenant, value, local=True)


async def operation_for_run(reader, actor, tenant, raw):
    value = stored_selection(raw)
    await confirm_selection(reader, actor, tenant, value)
    return SourceReadOperation(actor, tenant, value.snapshot(), reader), value
