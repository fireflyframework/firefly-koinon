# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fleet-wide rolling limits delegated to native PostgreSQL coordination."""

from datetime import timedelta

from pyfly.cache import CacheAdapter, CacheCoordination

from flycanon.core.services.cache_support import cache_key, postgres_cache


class PostgresRateLimiter:
    def __init__(self, cache: CacheAdapter | None):
        dedicated = postgres_cache(cache, "canon.rate-limits.v1")
        if not isinstance(dedicated, CacheCoordination):
            raise RuntimeError("Native PostgreSQL CacheCoordination is required")
        self._coordination = dedicated

    @staticmethod
    def _key(token_id: str) -> str:
        return "rolling60-v1:" + cache_key(token_id)

    async def consume(self, *, token_id: str, limit_per_minute: int | None, now: float) -> bool:
        if limit_per_minute is None or limit_per_minute <= 0:
            return True
        return await self._coordination.consume_window(
            self._key(token_id), limit_per_minute, timedelta(seconds=60)
        )

    async def drop(self, token_id: str) -> None:
        await self._coordination.clear_window(self._key(token_id))
