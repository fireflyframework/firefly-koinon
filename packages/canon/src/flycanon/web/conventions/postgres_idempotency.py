# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed replay responses and legacy entries in disjoint native cache namespaces."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pyfly.cache import CacheAdapter

from flycanon.core.services.cache_support import (
    CacheCodec,
    ManagedCacheBridge,
    cache_key,
    isolated_cache_call,
    postgres_cache,
)
from flycanon.web.conventions.idempotency import (
    DEFAULT_IDEMPOTENCY_TTL,
    IdempotencyEntry,
    IdempotencyKey,
    StoredResponse,
)


class PostgresIdempotencyStore(ManagedCacheBridge):
    def __init__(self, cache: CacheAdapter | None, *, timeout_seconds: float = 5):
        super().__init__(timeout_seconds=timeout_seconds)
        self._responses = postgres_cache(cache, "canon.idempotency.responses.v1")
        self._legacy = postgres_cache(cache, "canon.idempotency.legacy.v1")
        self._response_codec = CacheCodec[StoredResponse]("response.v1", StoredResponse)
        self._entry_codec = CacheCodec[IdempotencyEntry]("entry.v1", IdempotencyEntry)

    def get(
        self, tenant_id: str, workspace_id: str, route: str, key: IdempotencyKey
    ) -> IdempotencyEntry | None:
        raw = self.call(lambda: self._legacy.get(cache_key(tenant_id, workspace_id, route, key.value)))
        if raw is None:
            return None
        entry = self._entry_codec.decode(raw)
        return entry if entry.expires_at > datetime.now(UTC) else None

    def put(self, entry: IdempotencyEntry) -> None:
        key = cache_key(entry.tenant_id, entry.workspace_id, entry.route, entry.key.value)
        ttl = entry.expires_at - datetime.now(UTC)
        if ttl.total_seconds() <= 0:
            self.call(lambda: self._legacy.evict(key))
        else:
            value = self._entry_codec.encode(entry)
            self.call(lambda: self._legacy.put(key, value, ttl))

    async def lookup(self, *, tenant_id: str, route: str, key: str) -> StoredResponse | None:
        if not key:
            return None
        IdempotencyKey(key)
        raw = await isolated_cache_call(lambda: self._responses.get(cache_key(tenant_id, route, key)))
        return self._response_codec.decode(raw) if raw is not None else None

    async def record_response(
        self, *, tenant_id: str, route: str, key: str, status: int, json_body: dict[str, Any] | list[Any]
    ) -> None:
        if not key:
            return
        IdempotencyKey(key)
        value = self._response_codec.encode(StoredResponse(status, json_body))
        await isolated_cache_call(
            lambda: self._responses.put_if_absent(
                cache_key(tenant_id, route, key), value, DEFAULT_IDEMPOTENCY_TTL
            )
        )
