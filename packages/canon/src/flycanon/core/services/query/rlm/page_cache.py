# Copyright 2024-2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared page text over scoped verified-original keys supplied by the corpus builder.

PostgreSQL uses the managed primary cache and application event loop. Explicit Redis compatibility
and isolated-development memory implementations retain the synchronous worker-thread protocol.
Versioned document views continue through their immutable authorized reader rather than this cache.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pyfly.cache import CacheAdapter

if TYPE_CHECKING:
    import redis

from flycanon.config import CanonSettings
from flycanon.core.services.cache_support import CacheCodec, ManagedCacheBridge, cache_backend, postgres_cache

logger = logging.getLogger(__name__)


# Clock-source injection so tests can drive TTL expiry without sleeping.
NowFn = Callable[[], float]


@runtime_checkable
class CorpusPageCache(Protocol):
    """Synchronous page-text cache: ``content_sha256 -> page list``.

    Both backends satisfy this structurally. ``get`` returns the cached
    page list or ``None`` on a miss (or an expired entry); ``set``
    stores a page list under the key.
    """

    def get(self, key: str) -> list[str] | None: ...

    def set(self, key: str, pages: list[str]) -> None: ...


@dataclass(slots=True)
class _Entry:
    """A cached page list plus the monotonic time it expires at."""

    pages: list[str]
    expires_at: float


class MemoryPageCache:
    """Thread-safe, bounded LRU page cache with per-entry TTL.

    :param ttl_s: Per-entry time-to-live in seconds.
    :param max_entries: LRU cap. When the cache is full and a new entry
        lands, the least-recently-used entry is dropped.
    :param now_fn: Clock-source override (defaults to
        :func:`time.monotonic`); tests inject a stub to drive TTL expiry
        without sleeping.

    The cache is a process singleton hit by concurrent REPL worker
    threads, so a single coarse-grained :class:`threading.Lock` guards
    every read and write of the underlying :class:`OrderedDict`.
    """

    def __init__(
        self,
        *,
        ttl_s: int,
        max_entries: int,
        now_fn: NowFn | None = None,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be > 0")
        self._ttl = int(ttl_s)
        self._max_entries = int(max_entries)
        self._now: NowFn = now_fn or time.monotonic
        self._cache: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> list[str] | None:
        """Return the cached pages for ``key`` or ``None`` (miss / expired)."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if self._now() >= entry.expires_at:
                # Expired -- drop it lazily; caller refetches + repopulates.
                self._cache.pop(key, None)
                return None
            # Refresh LRU order on hit.
            self._cache.move_to_end(key)
            return list(entry.pages)

    def set(self, key: str, pages: list[str]) -> None:
        """Store ``pages`` under ``key``, applying TTL + LRU eviction."""
        with self._lock:
            # Re-insert after pop so the OrderedDict order is honest.
            self._cache.pop(key, None)
            self._cache[key] = _Entry(pages=list(pages), expires_at=self._now() + self._ttl)
            while len(self._cache) > self._max_entries:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug("corpus_page_cache_lru_evict key=%s", evicted_key)


class RedisPageCache:
    """Redis-backed shared page cache: page list as JSON with ``EX = ttl``.

    :param client: A synchronous :class:`redis.Redis` client.
    :param ttl_s: TTL applied to every key so Redis evicts entries
        natively -- no in-process LRU cap needed.
    :param prefix: Key prefix so flycanon shares a Redis instance with
        other Firefly services without colliding.

    The client is synchronous (NOT ``redis.asyncio``) because the cache
    is read from the RLM engine's worker thread.
    """

    def __init__(self, client: redis.Redis, *, ttl_s: int, prefix: str = "canon:pages:") -> None:
        self._client = client
        self._ttl = int(ttl_s)
        self._prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> list[str] | None:
        """Return the cached pages for ``key`` or ``None`` on a miss."""
        raw = self._client.get(self._key(key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return list(json.loads(raw))

    def set(self, key: str, pages: list[str]) -> None:
        """Store ``pages`` as JSON under ``key`` with ``EX = ttl_s``."""
        self._client.set(self._key(key), json.dumps(pages), ex=self._ttl)


class PostgresPageCache(ManagedCacheBridge):
    """Typed page lists in a dedicated native cache, accessed from RLM worker threads."""

    def __init__(self, cache: CacheAdapter | None, *, ttl_s: int, timeout_seconds: float = 5):
        super().__init__(timeout_seconds=timeout_seconds)
        if type(ttl_s) is not int or ttl_s < 0:
            raise ValueError("Corpus cache TTL must be a nonnegative integer")
        self._cache = postgres_cache(cache, "canon.corpus-pages.v1")
        self._ttl = timedelta(seconds=ttl_s)
        self._codec = CacheCodec[list[str]]("corpus-pages.v1", list[str])

    def get(self, key: str) -> list[str] | None:
        if self._ttl <= timedelta(0):
            return None
        raw = self.call(lambda: self._cache.get(key))
        return self._codec.decode(raw) if raw is not None else None

    def set(self, key: str, pages: list[str]) -> None:
        if self._ttl > timedelta(0):
            value = self._codec.encode(pages)
            self.call(lambda: self._cache.put(key, value, self._ttl))


def build_page_cache(settings: CanonSettings, cache: CacheAdapter | None = None) -> CorpusPageCache:
    """Select the declared backend; no availability-based fallback is permitted."""
    backend = cache_backend(settings, "corpus_cache_backend")
    if backend == "postgres":
        return PostgresPageCache(cache, ttl_s=settings.corpus_cache_ttl_s)
    if backend == "redis":
        import redis

        return RedisPageCache(redis.Redis.from_url(settings.redis_url), ttl_s=settings.corpus_cache_ttl_s)
    return MemoryPageCache(ttl_s=settings.corpus_cache_ttl_s, max_entries=settings.corpus_cache_max_entries)


__all__ = [
    "CorpusPageCache",
    "MemoryPageCache",
    "NowFn",
    "PostgresPageCache",
    "RedisPageCache",
    "build_page_cache",
]
