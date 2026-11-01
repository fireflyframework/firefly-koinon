# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio

import pytest
from pyfly.cache.adapters.postgres import PostgresCacheAdapter
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry

from flycanon.config import CanonSettings
from flycanon.core.services.query.rlm.page_cache import PostgresPageCache, build_page_cache


async def test_pg_pages_cross_instances_and_root_clear_cannot_delete_them(tmp_path):
    registry = DataSourceRegistry(
        Config({"pyfly": {"data": {"relational": {"url": f"sqlite+aiosqlite:///{tmp_path / 'pages.db'}"}}}})
    )
    native = PostgresCacheAdapter(registry.primary)
    await native.start()
    first, second = (
        build_page_cache(CanonSettings(redis_url="redis://ignored.invalid"), native) for _ in range(2)
    )
    try:
        assert isinstance(first, PostgresPageCache) and isinstance(second, PostgresPageCache)
        first.bind_loop()
        second.bind_loop()
        pages = ["verified scoped original"]
        await asyncio.to_thread(first.set, "scope-reader-original", pages)
        pages.append("caller change")
        assert await asyncio.to_thread(second.get, "scope-reader-original") == ["verified scoped original"]
        await native.clear()
        assert await asyncio.to_thread(second.get, "scope-reader-original") == ["verified scoped original"]
        await asyncio.to_thread(first.set, "scope-reader-original", ["replacement"])
        assert await asyncio.to_thread(second.get, "scope-reader-original") == ["replacement"]
        with pytest.raises(RuntimeError, match="worker thread"):
            first.get("scope-reader-original")
    finally:
        await first.close_bridge()
        await second.close_bridge()
        await registry.close()


def test_page_factory_never_uses_a_silent_memory_or_redis_fallback():
    for settings in (CanonSettings(), CanonSettings(redis_url="redis://ignored.invalid")):
        with pytest.raises(RuntimeError, match="primary"):
            build_page_cache(settings)
    with pytest.raises(RuntimeError, match="isolated"):
        build_page_cache(CanonSettings(corpus_cache_backend="memory", allow_in_memory_adapters=False))
