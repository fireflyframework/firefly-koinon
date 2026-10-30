# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operation leases and cancellation-draining disposal for owned SDK clients."""

import asyncio
import threading
from collections.abc import Awaitable, Callable, Iterator
from concurrent.futures import Future
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from functools import wraps
from typing import Concatenate, Protocol


class ClientLifecycle:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._depth: ContextVar[int] = ContextVar("storage_operation_depth", default=0)
        self._active = 0
        self._closing = False
        self._closed = False
        self._drained: Future[None] = Future()
        self._shutdown_complete: Future[None] = Future()

    @property
    def closing(self) -> bool:
        with self._lock:
            return self._closing

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @contextmanager
    def operation(self) -> Iterator[None]:
        depth = self._depth.get()
        if depth == 0:
            with self._lock:
                if self._closing:
                    raise RuntimeError("Storage client is closed")
                self._active += 1
        token = self._depth.set(depth + 1)
        try:
            yield
        finally:
            self._depth.reset(token)
            if depth == 0:
                with self._lock:
                    self._active -= 1
                    if self._closing and self._active == 0 and not self._drained.done():
                        self._drained.set_result(None)

    @staticmethod
    async def _await_task[T](task: asyncio.Future[T]) -> T:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            with suppress(Exception):
                task.result()
            raise

    @classmethod
    async def _await_worker[T](cls, function: Callable[[], T]) -> T:
        return await cls._await_task(asyncio.create_task(asyncio.to_thread(function)))

    async def run[T](self, function: Callable[[], T]) -> T:
        with self.operation():
            return await self._await_worker(function)

    async def close(self, release: Callable[[], None]) -> None:
        await self.aclose(lambda: self._await_worker(release))

    async def aclose(self, release: Callable[[], Awaitable[None]]) -> None:
        with self._lock:
            if self._closed:
                return
            owner = not self._closing
            self._closing = True
            if self._active == 0 and not self._drained.done():
                self._drained.set_result(None)

        async def shutdown() -> None:
            # Draining must not occupy a worker needed by admitted verification.
            await asyncio.wrap_future(self._drained)
            try:
                await release()
            finally:
                with self._lock:
                    self._closed = True
                    self._shutdown_complete.set_result(None)

        task = asyncio.create_task(shutdown()) if owner else asyncio.wrap_future(self._shutdown_complete)
        await self._await_task(task)


class _LifecycleOwner(Protocol):
    _lifecycle: ClientLifecycle


def client_operation[Owner: _LifecycleOwner, **P, R](
    function: Callable[Concatenate[Owner, P], Awaitable[R]],
) -> Callable[Concatenate[Owner, P], Awaitable[R]]:
    @wraps(function)
    async def operation(self: Owner, *args: P.args, **kwargs: P.kwargs) -> R:
        with self._lifecycle.operation():
            return await function(self, *args, **kwargs)

    return operation
