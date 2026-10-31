# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bound root operations before claims; native permits cover their complete lifetime."""

import asyncio
import math
from collections import deque
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

from pyfly.container import component, service
from pyfly.core import config_properties
from pyfly.kernel import ServiceUnavailableException
from pyfly.resilience import Bulkhead

WorkKind = Literal[
    "conversation",
    "index",
    "attachment",
    "profile",
    "document",
    "structured",
    "callback",
    "query",
    "maintenance",
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
    api_capacity: int = 1
    max_waiters: int = 64
    wait_timeout_seconds: float = 30

    def __post_init__(self):
        for value, maximum in ((self.worker_capacity, 32), (self.api_capacity, 64), (self.max_waiters, 1024)):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("Work capacities and waiting limits must be bounded positive integers")
        value = self.wait_timeout_seconds
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 < value <= 300
        ):
            raise ValueError("Work admission timeout must be finite and between zero and 300 seconds")


class _Pool:
    def __init__(self, capacity, settings):
        self.bulkhead = Bulkhead(max_concurrent=capacity)
        self.settings = settings
        self.waiters: deque[asyncio.Future[None]] = deque()
        self.closed = False

    async def acquire(self):
        if self.closed:
            raise WorkAdmissionUnavailable()
        if not self.waiters and self.bulkhead.available_slots:
            await self.bulkhead.acquire()
            return
        if len(self.waiters) >= self.settings.max_waiters:
            raise WorkAdmissionUnavailable()
        waiter = asyncio.get_running_loop().create_future()
        self.waiters.append(waiter)
        try:
            async with asyncio.timeout(self.settings.wait_timeout_seconds):
                await asyncio.shield(waiter)
        except BaseException as error:
            # A permit can be assigned in the same turn as cancellation or timeout.
            if waiter.done() and not waiter.cancelled() and waiter.exception() is None:
                await self.release()
            else:
                waiter.cancel()
                if waiter in self.waiters:
                    self.waiters.remove(waiter)
            if isinstance(error, TimeoutError):
                raise WorkAdmissionUnavailable() from None
            raise

    async def release(self):
        self.bulkhead.release()
        while not self.closed and self.waiters and self.bulkhead.available_slots:
            waiter = self.waiters.popleft()
            if not waiter.done():
                await self.bulkhead.acquire()
                waiter.set_result(None)

    def close(self):
        self.closed = True
        while self.waiters:
            waiter = self.waiters.popleft()
            if not waiter.done():
                waiter.set_exception(WorkAdmissionUnavailable())


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

    @property
    def worker_active(self):
        return self._workers.bulkhead.max_concurrent - self._workers.bulkhead.available_slots

    @property
    def worker_waiting(self):
        return len(self._workers.waiters)

    @property
    def api_active(self):
        return self._api.bulkhead.max_concurrent - self._api.bulkhead.available_slots

    def close_workers(self):
        self._workers.close()

    @asynccontextmanager
    async def hold(self, kind: WorkKind, *, api: bool = False):
        if kind not in {
            "conversation",
            "index",
            "attachment",
            "profile",
            "document",
            "structured",
            "callback",
            "query",
            "maintenance",
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
        pool = self._api if api else self._workers
        await pool.acquire()
        reservation = _Reservation(self, pool)
        token = _current.set(reservation)
        try:
            yield
        finally:
            reservation.open = False
            _current.reset(token)
            await reservation.release()
