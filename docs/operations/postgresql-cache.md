<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Shared PostgreSQL cache

koinon uses the primary PostgreSQL datasource for its cache by default. API replicas and workers share the same entries and admission counters through pyfly's native cache adapter. The default installation does not require a Redis service, another database credential or a separate cache connection pool.

## Configure the installation

The default configuration is:

```yaml
pyfly:
  cache:
    enabled: true
    provider: postgres
    postgres:
      datasource: primary
  data:
    relational:
      enabled: true
      ddl-auto: validate
      url: ${KOINON_DATABASE_URL}
```

`primary` names the application's registered datasource. Cache operations inherit its TLS configuration and pool limits. The document and structured datasource roles do not need access to framework cache tables. The product document and structured adapters require this managed primary binding. The framework also supports other explicitly registered datasources for independent cache consumers; selecting one does not relocate the product adapters automatically.

The equivalent product environment settings are `KOINON_CACHE_ENABLED=true`, `KOINON_CACHE_PROVIDER=postgres` and `KOINON_CACHE_DATASOURCE=primary`. Unknown providers and unavailable backing stores produce a configuration or operation failure. They do not select an in-memory replacement.

Cache selection is an installation setting. It does not change an organization's knowledge scope, authorization rules or model assignments.

## Understand what is stored

| Data | Storage and behavior |
| --- | --- |
| Cached values and replay responses | `pyfly_cache_entries`, with typed JSON serialization and an expiry time. |
| Shared rolling admission windows | `pyfly_cache_windows`, separate from evictable values. |
| Original files and durable knowledge | Their configured object stores and versioned knowledge tables. Cache cleanup does not replace or delete these records. |

Each document, structured, replay and corpus consumer uses a dedicated namespace. A normal cache clear cannot remove another namespace or reset admission windows. Replay responses retain their original response for the configured replay lifetime. A cached response is not an execution reservation: current authorization and the operation's own revision, approval and idempotency requirements still apply.

Corpus caching preserves the authorized source identity and extraction key. It does not make content available to another user or publish derived knowledge. Historical answers continue to use their immutable evidence rather than whichever entry is currently cached.

## Operate across replicas

PostgreSQL supplies expiry time for the default adapter. TTL values represent elapsed time, including across daylight saving changes. Admission uses a database clock read after acquiring the key's lock, so replicas share one rolling window. Coordination uses a short transaction on the primary datasource and does not inherit a caller's replica snapshot or roll back with an unrelated business transaction.

Expired records are removed in bounded batches. Live entries renewed by another process are preserved during cleanup. Keep the primary pool and PostgreSQL connection budget in the API/worker sizing plan, and monitor request latency and expired-row backlog. Cache operations borrow the existing pool; they do not create an additional unbounded engine.

If PostgreSQL becomes unavailable, replay and rate-limit operations fail instead of silently losing their shared state. Restore service connectivity and inspect the recorded operation outcome before retrying a write. Do not clear counters or recreate tables to make a failed request succeed.

## Upgrade an existing installation

Use the matching release's [native migration bundle](migrations.md). Native migration 34 adds `pyfly_cache_windows`; it preserves the existing cache table, knowledge tables and migration history. Apply the current scoped grants before restarting API replicas or workers with runtime schema validation enabled.

Back up retained data and test the upgrade on an isolated copy first. Check that two instances share cached values and the same admission limit, that ordinary cache eviction preserves that limit, and that replacement workloads retain their state. See [first start](first-start.md) and [worker roles and scaling](workers.md).
