# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One operation's candidate reuse; authority and database hydration are never retained."""

from asyncio import Task, current_task
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from pyfly.kernel import ServiceUnavailableException

from flycanon.core.agents.model_bindings import BindingScope, current_scope
from flycanon.core.services.query import provenance
from flycanon.core.services.retrieval.fusion import ChunkHit


@dataclass(frozen=True)
class RankedCandidate:
    chunk_id: str
    score: float


@dataclass
class CandidateScope:
    task: Task[Any]
    connections: BindingScope
    observation: provenance.Observation
    policy_digest: str | None
    active: bool = True
    key: tuple | None = None
    candidates: tuple[RankedCandidate, ...] | None = None

    def check(self) -> None:
        if (
            not self.active
            or current_task() is not self.task
            or self.task.cancelling()
            or current_scope() is not self.connections
            or provenance.current() is not self.observation
        ):
            raise ServiceUnavailableException(
                "Native candidate operation has ended", code="KNOWLEDGE_RETRIEVAL_SCOPE_EXPIRED"
            )

    def clear(self) -> None:
        self.key, self.candidates = None, None


_current: ContextVar[CandidateScope | None] = ContextVar("native_candidate_reuse", default=None)


@contextmanager
def candidate_scope(*, policy_digest: str | None) -> Iterator[None]:
    connections, observation = current_scope(), provenance.current()
    task = current_task()
    scope = (
        CandidateScope(task, connections, observation, policy_digest)
        if task is not None and connections is not None and observation is not None
        else None
    )
    token = _current.set(scope)
    try:
        yield
    finally:
        if scope is not None:
            scope.active = False
            scope.clear()
        _current.reset(token)


async def candidates(
    key: tuple,
    retrieve: Callable[[], Awaitable[list[ChunkHit]]],
    *,
    complete: Callable[[], bool],
    reload: Callable[[tuple[RankedCandidate, ...]], Awaitable[list[ChunkHit]]],
) -> list[ChunkHit]:
    scope = _current.get()
    if scope is None:
        return await retrieve()
    try:
        scope.check()
        key = (scope.policy_digest, key)
        if scope.key == key and scope.candidates is not None:
            await provenance.authorize()
            scope.check()
            result = await reload(scope.candidates)
            scope.check()
            return result
        result = await retrieve()
        scope.check()
        if complete():
            scope.key = key
            scope.candidates = tuple(RankedCandidate(hit.chunk_id, hit.score) for hit in result)
        else:
            scope.clear()
        return result
    except BaseException:
        scope.clear()
        raise
