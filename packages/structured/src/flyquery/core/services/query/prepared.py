# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Task-owned private query preparation and explicit local publication."""

import asyncio
import copy
import json
import uuid
from dataclasses import dataclass, field

from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ServiceUnavailableException

from flyquery.core.services.query.consumer_context import consumer_context


def no_query_unit():
    for name in (None, "primary", "structured", "canon"):
        unit = current_unit_of_work(name)
        if unit is not None and not unit.completed:
            raise ServiceUnavailableException(
                "Query preparation has an ambient unit", code="QUERY_UNIT_INVALID"
            )


@dataclass
class PreparedQuery:
    query_id: uuid.UUID = field(default_factory=uuid.uuid4)
    answer: object = None
    _writes: list = field(default_factory=list, repr=False)
    _task: object = field(default_factory=asyncio.current_task, repr=False)
    _consumer: object = field(default_factory=consumer_context, repr=False)
    _state: str = "preparing"
    artifacts: set[str] = field(default_factory=set, repr=False)

    async def abort_preparation(self, store):
        """Delete only this unpublished operation's known private objects."""
        no_query_unit()
        if self._state != "preparing" or self._task is not asyncio.current_task():
            return
        self._state = "failed"
        try:
            async with asyncio.timeout(5):
                for key in self.artifacts:
                    await store.delete(key)
        except Exception:
            # An uncertain deletion remains private for normal retention.
            return

    def bind_manifest(self, pins):
        if self._state != "ready" or self._task is not asyncio.current_task():
            raise ServiceUnavailableException("Prepared query expired", code="QUERY_PREPARATION_INVALID")
        for kind, fields in self._writes:
            if kind == "query":
                fields["table_id_snapshot_pins_json"] = copy.deepcopy(pins)

    def stage(self, kind, values):
        no_query_unit()
        if self._state != "preparing" or self._task is not asyncio.current_task():
            raise ServiceUnavailableException("Prepared query expired", code="QUERY_PREPARATION_INVALID")
        if len(self._writes) >= 4 or len(json.dumps(values, default=str).encode()) > 16 * 1024 * 1024:
            raise ServiceUnavailableException(
                "Prepared query exceeds its bound", code="QUERY_PREPARATION_INVALID"
            )
        self._writes.append((kind, copy.deepcopy(values)))

    def seal(self, answer):
        no_query_unit()
        if self._state != "preparing" or self._task is not asyncio.current_task():
            raise ServiceUnavailableException("Prepared query expired", code="QUERY_PREPARATION_INVALID")
        if str(answer.query_id) != str(self.query_id):
            raise ServiceUnavailableException(
                "Prepared query identity changed", code="QUERY_PREPARATION_INVALID"
            )
        self.answer = copy.deepcopy(answer)
        self._state = "ready"

    def invalidate(self):
        no_query_unit()
        if self._task is not asyncio.current_task():
            raise ServiceUnavailableException("Prepared query expired", code="QUERY_PREPARATION_INVALID")
        self._state = "failed"

    async def publish(self, query_repository, conversation_service, examples_repository):
        if (
            self._state != "ready"
            or self._task is not asyncio.current_task()
            or self._consumer != consumer_context()
        ):
            raise ServiceUnavailableException("Prepared query expired", code="QUERY_PREPARATION_INVALID")
        self._state = "consumed"
        unit = current_unit_of_work("structured")
        if unit is None or unit.completed or unit.read_only:
            raise ServiceUnavailableException(
                "An explicit native publication unit is required", code="QUERY_UNIT_INVALID"
            )
        for kind, fields in self._writes:
            if kind == "query":
                result = await query_repository.create_query(**fields)
                if result != self.query_id:
                    raise ServiceUnavailableException(
                        "Published query identity changed", code="QUERY_PREPARATION_INVALID"
                    )
            elif kind == "result":
                await query_repository.upsert_result(**fields)
            elif kind == "turn":
                await conversation_service.append_turn(**fields)
            elif kind == "example":
                await examples_repository.create(**fields)
        return copy.deepcopy(self.answer)


class DeferredQueries:
    def __init__(self, prepared):
        self.prepared = prepared

    async def create_query(self, **fields):
        self.prepared.stage("query", {**fields, "query_id": self.prepared.query_id})
        return self.prepared.query_id

    async def upsert_result(self, **fields):
        self.prepared.stage("result", fields)


class DeferredConversation:
    def __init__(self, prepared, service):
        self.prepared, self.service = prepared, service

    async def last_turn(self, conversation_id):
        return await self.service.last_turn(conversation_id)

    async def append_turn(self, **fields):
        self.prepared.stage("turn", {**fields, "query_id": self.prepared.query_id})


class DeferredExamples:
    def __init__(self, prepared):
        self.prepared = prepared

    async def create(self, **fields):
        self.prepared.stage("example", fields)
        return copy.deepcopy(fields)
