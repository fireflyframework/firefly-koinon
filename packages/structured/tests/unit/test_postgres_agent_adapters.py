# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native primary cache contracts; no Redis server or external provider is used."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.cache.adapters.postgres import PostgresCacheAdapter
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry

from flyquery.config import FlyquerySettings
from flyquery.core.configuration import FlyqueryConfiguration
from flyquery.core.services.auth.postgres_rate_limiter import PostgresRateLimiter
from flyquery.web.conventions.idempotency import IdempotencyEntry, IdempotencyKey
from flyquery.web.conventions.postgres_idempotency import PostgresIdempotencyStore


@pytest.fixture
async def primary_cache(tmp_path):
    registry = DataSourceRegistry(
        Config({"pyfly": {"data": {"relational": {"url": f"sqlite+aiosqlite:///{tmp_path / 'cache.db'}"}}}})
    )
    cache = PostgresCacheAdapter(registry.primary)
    await cache.start()
    try:
        yield cache
    finally:
        await registry.close()


async def test_default_factories_use_native_primary_even_with_a_redis_url(primary_cache, monkeypatch):
    import flyquery.core.configuration as configuration

    monkeypatch.setattr(
        configuration, "_build_redis_client", lambda _: pytest.fail("Implicit Redis selected")
    )
    settings = FlyquerySettings(redis_url="redis://unreachable.invalid:6379")
    factory = FlyqueryConfiguration()
    assert isinstance(factory.rate_limiter(settings, primary_cache), PostgresRateLimiter)
    assert isinstance(factory.idempotency_store(settings, primary_cache), PostgresIdempotencyStore)
    with pytest.raises(RuntimeError, match="primary"):
        factory.idempotency_store(settings)
    with pytest.raises(RuntimeError, match="isolated"):
        factory.idempotency_store(
            FlyquerySettings(idempotency_backend="memory", allow_in_memory_adapters=False), primary_cache
        )


async def test_two_stores_keep_first_response_typed_and_separate_tuple_keys(primary_cache):
    first, second = PostgresIdempotencyStore(primary_cache), PostgresIdempotencyStore(primary_cache)
    await asyncio.gather(
        *(
            store.record_response(
                tenant_id="tenant", route="route", key="same", status=202, json_body={"winner": index}
            )
            for index, store in enumerate((first, second) * 5)
        )
    )
    result = await first.lookup(tenant_id="tenant", route="route", key="same")
    assert result is not None and result.status == 202
    winner = dict(result.body)
    result.body["winner"] = "caller mutation"
    await second.record_response(
        tenant_id="tenant", route="route", key="same", status=500, json_body={"winner": "later"}
    )
    assert (await second.lookup(tenant_id="tenant", route="route", key="same")).body == winner
    await first.record_response(tenant_id="a:b", route="c", key="key", status=201, json_body={"slot": 1})
    await first.record_response(tenant_id="a", route="b:c", key="key", status=200, json_body={"slot": 2})
    assert (await first.lookup(tenant_id="a:b", route="c", key="key")).body == {"slot": 1}
    assert (await first.lookup(tenant_id="a", route="b:c", key="key")).body == {"slot": 2}
    await primary_cache.clear()
    assert (await second.lookup(tenant_id="tenant", route="route", key="same")).body == winner


async def test_legacy_sync_surface_uses_bound_application_loop_and_preserves_workspace(primary_cache):
    store = PostgresIdempotencyStore(primary_cache)
    store.bind_loop()
    entry = IdempotencyEntry(
        "tenant",
        "workspace",
        "route",
        IdempotencyKey("key"),
        "hash",
        "job",
        datetime.now(UTC) + timedelta(minutes=1),
    )
    await asyncio.to_thread(store.put, entry)
    restored = await asyncio.to_thread(store.get, "tenant", "workspace", "route", entry.key)
    assert restored == entry and restored is not entry
    assert await asyncio.to_thread(store.get, "tenant", "other", "route", entry.key) is None
    assert await store.lookup(tenant_id="tenant", route="route", key="key") is None
    with pytest.raises(RuntimeError, match="worker thread"):
        store.get("tenant", "workspace", "route", entry.key)
    await store.close_bridge()
    with pytest.raises(RuntimeError, match="event loop"):
        await asyncio.to_thread(store.get, "tenant", "workspace", "route", entry.key)


async def test_rate_window_and_drop_share_versioned_namespaced_key(primary_cache, monkeypatch):
    calls = []

    async def consume(cache, key, limit, window):
        calls.append((cache.namespace, key, limit, window))
        return True

    async def clear(cache, key):
        calls.append((cache.namespace, key))
        return True

    monkeypatch.setattr(PostgresCacheAdapter, "consume_window", consume)
    monkeypatch.setattr(PostgresCacheAdapter, "clear_window", clear)
    limiter = PostgresRateLimiter(primary_cache)
    for limit in (None, 0, -1):
        assert await limiter.consume(token_id="token", limit_per_minute=limit, now=0)
    assert not calls
    assert await limiter.consume(token_id="token", limit_per_minute=3, now=float("nan"))
    await limiter.drop("token")
    assert calls[0][0] != primary_cache.namespace
    assert calls[0][:2] == calls[1] and calls[0][2:] == (3, timedelta(seconds=60))
    assert "60" in calls[0][1]


async def test_sync_bridge_timeout_and_shutdown_drain_owned_operations():
    from flyquery.core.services.cache_support import ManagedCacheBridge

    bridge = ManagedCacheBridge(timeout_seconds=0.05)
    bridge.bind_loop()
    entered, drained = asyncio.Event(), asyncio.Event()

    async def waiting():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            drained.set()

    with pytest.raises(TimeoutError, match="deadline"):
        await asyncio.to_thread(bridge.call, waiting)
    assert entered.is_set() and drained.is_set() and not bridge._pending
    drained.clear()
    caller = asyncio.create_task(asyncio.to_thread(bridge.call, waiting))
    await asyncio.sleep(0.01)
    await bridge.close_bridge()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert drained.is_set() and not bridge._pending


async def test_native_application_context_binds_managed_cache_and_bridge_lifecycle(tmp_path):
    from pyfly.cache import CacheAdapter
    from pyfly.cache.auto_configuration import CacheAutoConfiguration
    from pyfly.container import bean, configuration
    from pyfly.context.application_context import ApplicationContext

    @configuration
    class DomainCaches:
        @bean
        def replay(self, cache: CacheAdapter) -> PostgresIdempotencyStore:
            return FlyqueryConfiguration().idempotency_store(
                FlyquerySettings(redis_url="redis://ignored.invalid"), cache
            )

        @bean
        def rate(self, cache: CacheAdapter) -> PostgresRateLimiter:
            return FlyqueryConfiguration().rate_limiter(FlyquerySettings(), cache)

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "enabled": False,
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'native.db'}",
                            "ddl-auto": "create",
                        }
                    },
                    "cache": {"enabled": True, "postgres": {"datasource": "primary"}},
                }
            }
        )
    )
    context.register_bean(CacheAutoConfiguration)
    context.register_bean(DomainCaches)
    await context.start()
    try:
        store = context.get_bean(PostgresIdempotencyStore)
        assert isinstance(context.get_bean(CacheAdapter), PostgresCacheAdapter)
        assert isinstance(context.get_bean(PostgresRateLimiter), PostgresRateLimiter)
        assert store._loop is asyncio.get_running_loop()
        await store.record_response(tenant_id="t", route="r", key="k", status=200, json_body={"ok": True})
        assert (await store.lookup(tenant_id="t", route="r", key="k")).body == {"ok": True}
    finally:
        await context.stop()
    assert store._closed
