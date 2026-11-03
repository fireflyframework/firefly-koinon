# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bound root operations before claims; native permits cover their complete lifetime."""

import math
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

from pyfly.container import component, service
from pyfly.core import config_properties
from pyfly.kernel import BulkheadException, ServiceUnavailableException
from pyfly.resilience import QueuedBulkhead

WorkKind = Literal[
    "conversation",
    "index",
    "attachment",
    "profile",
    "communications",
    "document",
    "structured",
    "callback",
    "query",
    "maintenance",
    "bulk",
]


class WorkAdmissionUnavailable(ServiceUnavailableException):
    def __init__(self):
        super().__init__(
            "This process is at its work capacity; retry later", code="WORK_CAPACITY_UNAVAILABLE"
        )


@component(name="operations.work_admission_settings")
@config_properties(prefix="koinon.operations.admission")
@dataclass
class WorkAdmissionSettings:
    worker_capacity: int = 1
    conversation_capacity: int = 0
    api_capacity: int = 1
    max_waiters: int = 64
    wait_timeout_seconds: float = 30

    def __post_init__(self):
        for value, maximum in ((self.worker_capacity, 32), (self.api_capacity, 64), (self.max_waiters, 1024)):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("Work capacities and waiting limits must be bounded positive integers")
        if type(self.conversation_capacity) is not int or not 0 <= self.conversation_capacity <= 16:
            raise ValueError("Reserved conversation capacity must be an integer from zero through 16")
        value = self.wait_timeout_seconds
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 < value <= 300
        ):
            raise ValueError("Work admission timeout must be finite and between zero and 300 seconds")

    @property
    def process_capacity(self) -> int:
        return self.worker_capacity + self.conversation_capacity

    def capacity_for(self, kind: str) -> int:
        if kind == "conversation" and self.conversation_capacity:
            return self.conversation_capacity
        return self.worker_capacity


class _Pool:
    def __init__(self, capacity, settings):
        self.bulkhead = QueuedBulkhead(
            max_concurrent=capacity,
            max_waiters=settings.max_waiters,
            wait_timeout_seconds=settings.wait_timeout_seconds,
        )

    async def acquire(self):
        try:
            await self.bulkhead.acquire()
        except BulkheadException:
            raise WorkAdmissionUnavailable() from None

    async def release(self):
        self.bulkhead.release()

    def close(self):
        self.bulkhead.close()


@dataclass
class _Reservation:
    owner: object
    pool: _Pool
    open: bool = True
    references: int = 1

    async def release(self):
        self.references -= 1
        if self.references == 0:
            await self.pool.release()


_current: ContextVar[_Reservation | None] = ContextVar("koinon.work_reservation", default=None)


@service(name="operations.work_admission")
class WorkAdmission:
    def __init__(self, settings: WorkAdmissionSettings):
        settings.__post_init__()
        self._workers, self._api = (
            _Pool(settings.worker_capacity, settings),
            _Pool(settings.api_capacity, settings),
        )
        self._conversations = (
            _Pool(settings.conversation_capacity, settings) if settings.conversation_capacity else None
        )

    def _worker_pools(self):
        return (self._workers, self._conversations) if self._conversations is not None else (self._workers,)

    @property
    def worker_active(self):
        return sum(pool.bulkhead.active_count for pool in self._worker_pools())

    @property
    def worker_waiting(self):
        return sum(pool.bulkhead.waiting_count for pool in self._worker_pools())

    @property
    def api_active(self):
        return self._api.bulkhead.active_count

    def close_workers(self):
        for pool in self._worker_pools():
            pool.close()

    @asynccontextmanager
    async def hold(self, kind: WorkKind, *, api: bool = False):
        if kind not in {
            "conversation",
            "index",
            "attachment",
            "profile",
            "communications",
            "document",
            "structured",
            "callback",
            "query",
            "maintenance",
            "bulk",
        }:
            raise ValueError("Work admission requires a declared operation kind")
        current = _current.get()
        if current is not None and current.owner is self:
            if not current.open:
                raise WorkAdmissionUnavailable()
            current.references += 1
            try:
                yield
            finally:
                await current.release()
            return
        pool = (
            self._api
            if api
            else (
                self._conversations
                if kind == "conversation" and self._conversations is not None
                else self._workers
            )
        )
        await pool.acquire()
        reservation = _Reservation(self, pool)
        token = _current.set(reservation)
        try:
            yield
        finally:
            reservation.open = False
            _current.reset(token)
            await reservation.release()
