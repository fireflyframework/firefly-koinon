# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed domain caches over the managed native primary and application loop."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import threading
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

from pyfly.cache import CacheAdapter
from pyfly.cache.adapters.postgres import PostgresCacheAdapter
from pyfly.cache.serialization import CacheValueError, cache_dumps, cache_loads, restore
from pyfly.context.lifecycle import post_construct, pre_destroy
from pyfly.data.relational.datasource_registry import datasource_of
from pyfly.data.transaction import outside_transaction


def cache_backend(settings: object, field: str) -> Literal["postgres", "redis", "memory"]:
    explicit = getattr(settings, field, "postgres")
    if not isinstance(explicit, str):
        raise ValueError(f"Unknown cache backend for {field}")
    selected = explicit.strip().lower()
    if selected in {"postgres", "postgresql", "auto"}:
        return "postgres"
    if selected == "redis":
        if not getattr(settings, "redis_url", ""):
            raise RuntimeError("Explicit Redis adapters require a configured Redis URL")
        return "redis"
    if selected in {"memory", "in_memory"}:
        if getattr(settings, "allow_in_memory_adapters", False) is not True:
            raise RuntimeError("Memory adapters require explicit isolated development configuration")
        return "memory"
    raise ValueError(f"Unknown cache backend for {field}")


def postgres_cache(cache: CacheAdapter | None, namespace: str) -> PostgresCacheAdapter:
    if not isinstance(cache, PostgresCacheAdapter):
        raise RuntimeError("Configure the native primary PostgreSQL CacheAdapter for domain caches")
    source = datasource_of(cache.engine)
    if source is None or source.name != "primary" or source.is_replica:
        raise RuntimeError("Domain caches require the managed native primary datasource")
    return cache.with_namespace(namespace)


def cache_key(*parts: str) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


class CacheCodec[T]:
    def __init__(self, schema: str, annotation: Any):
        self.schema, self.annotation = schema, annotation

    def encode(self, value: T) -> dict[str, Any]:
        return {"schema": self.schema, "value": cache_loads(cache_dumps(value))}

    def decode(self, value: Any) -> T:
        if not isinstance(value, dict) or set(value) != {"schema", "value"} or value["schema"] != self.schema:
            raise CacheValueError("Cached domain value has an incompatible schema")
        try:
            return cast(T, restore(value["value"], self.annotation))
        except (TypeError, ValueError):
            raise CacheValueError("Cached domain value does not match its declared type") from None


async def isolated_cache_call[T](operation: Callable[[], Awaitable[T]]) -> T:
    with outside_transaction():
        return await operation()


class ManagedCacheBridge:
    """Synchronous worker access uses the native application's existing event loop."""

    def __init__(self, *, timeout_seconds: float = 5):
        if (
            isinstance(timeout_seconds, bool)
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 30
        ):
            raise ValueError("Cache bridge deadline must be between zero and thirty seconds")
        self._timeout = timeout_seconds
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: int | None = None
        self._closed = False
        self._pending: set[asyncio.Task[Any]] = set()

    @post_construct
    def bind_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if self._closed or self._loop is not None and self._loop is not loop:
            raise RuntimeError("The native application event loop cannot be rebound")
        self._loop, self._loop_thread = loop, threading.get_ident()

    @pre_destroy
    async def close_bridge(self) -> None:
        self._closed = True
        tasks = tuple(self._pending)
        for task in tasks:
            task.cancel()
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=self._timeout)
            if pending:
                raise RuntimeError("Native cache operations did not drain before the deadline")

    async def _invoke[T](self, operation: Callable[[], Awaitable[T]], completed: threading.Event) -> T:
        task = asyncio.current_task()
        assert task is not None
        self._pending.add(task)
        try:
            if self._closed:
                raise RuntimeError("The native application event loop is closing")
            return await isolated_cache_call(operation)
        finally:
            self._pending.discard(task)
            completed.set()

    def call[T](self, operation: Callable[[], Awaitable[T]]) -> T:
        loop = self._loop
        if self._closed or loop is None or loop.is_closed() or not loop.is_running():
            raise RuntimeError(
                "A running native application event loop is required for synchronous cache access"
            )
        if threading.get_ident() == self._loop_thread:
            raise RuntimeError("Synchronous cache access requires a worker thread")
        completed = threading.Event()
        coroutine = self._invoke(operation, completed)
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        except BaseException:
            coroutine.close()
            raise
        try:
            return future.result(timeout=self._timeout)
        except TimeoutError:
            future.cancel()
            if not completed.wait(self._timeout):
                raise RuntimeError("Native cache cancellation did not drain before the deadline") from None
            raise TimeoutError("Native cache operation exceeded its deadline") from None
