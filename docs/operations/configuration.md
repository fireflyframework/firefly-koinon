# Operator configuration and observations

Set `KOINON_CONFIG_FILE` to a native YAML, TOML or JSON configuration file. Only the `koinon` and `pyfly` roots are read by the service entry point. Explicit product environment aliases override matching file fields; an absent alias preserves the configured file value, including identity endpoints, client secrets, false booleans and storage paths. Native configuration placeholders can resolve externally supplied environment values. Start from `deploy/production/configuration.yaml.example`; it contains no usable credentials.

Runtime DDL and automatic runtime migrations are prohibited. The service accepts schema policy `validate` or `none`; run the separate migration job before serving traffic. A runtime service must never receive the migration URL. Each named datasource is explicit: primary, document runtime/control, and structured runtime/control. Runtime roles must have neither superuser nor row-security bypass. Control roles have narrowly granted provisioning authority; they are not application request authority.

The authorized tenant configuration response includes a read-only `deployment` descriptor. Changing tenant model providers does not change deployment storage, datasource credentials or worker limits. Operator observations contain no connection URLs, credentials, filesystem paths or raw database errors. `available: null` means unverified or unknown; it must not render as ready. Every observation includes its timestamp and reason. A configured cloud bucket or registered model is insufficient evidence of availability.

Database observations use the existing native DataSourceRegistry and SQLAlchemy health indicator. Pool exhaustion preserves native `UNKNOWN` even when the aggregate status is `UP`. The role check verifies role flags, not all tenant policies; qualify actual tenant isolation separately. Pool usage reflects the current application process. Native metric registration does not prove an exporter is collecting data. The public `/ready` response remains small and requires a real catalog database query; `/health` reports process liveness.

Local storage observations use the settings already bound to the document and structured modules. The service creates one random probe file in an existing root, writes, flushes, reads and deletes only that file. It never creates a missing storage root. Results are cached for 20 seconds, and at most two local probes remain in flight; slow probes report unknown. Cloud storage is never contacted automatically. Mount and provision shared storage before starting replicas, and separately qualify provider permissions, encryption and recovery.

Vector observations use only the tenant's persisted workspace bindings under the native document tenant context, with explicit tenant/workspace predicates. They check the vector extension, embedding-set completion and physical valid/ready HNSW indexes. An empty binding, missing index, interrupted embedding set or exceeded verification limit cannot produce ready. Index creation belongs to privileged migrations or reviewed control operations, never runtime DDL.

## Bounded settings

| Alias | Default | Accepted range |
|---|---:|---:|
| `KOINON_DATABASE_POOL_SIZE` | 5 | 1–100 |
| `KOINON_DATABASE_POOL_MAX_OVERFLOW` | 0 | 0–100 |
| `KOINON_DATABASE_POOL_TIMEOUT` | 5 s | 0.1–120 s |
| `KOINON_DATABASE_POOL_RECYCLE` | 1800 s | -1–86400 s |
| `KOINON_DATABASE_POOL_PRE_PING` | false | boolean |
| `KOINON_WORKER_CONCURRENCY` | 1 | 1–16 |
| `KOINON_MAX_QUEUED_PER_SUBJECT` | 50 | 1–10000 |
| `KOINON_JOB_LEASE_SECONDS` | 60 s | 5–3600 s |
| `KOINON_MAX_INDEX_WORKSPACES` | 32 | 1–128 |
| `KOINON_ASSISTANT_LEASE_SECONDS` | 60 s | 5–3600 s |
| `KOINON_ASSISTANT_RUN_TIMEOUT` | 180 s | 10–3600 s |
| `KOINON_ASSISTANT_MAX_HISTORY_MESSAGES` | 40 | 2–200 |
| `KOINON_TOKEN_MAX_ACTIVE_PER_USER` | 100 | 1–10000 |
| `KOINON_TOKEN_MAX_LIFETIME_DAYS` | 365 | 1–3650 |

Each named datasource supports the same pool aliases with `DATABASE` replaced by its exact uppercase name: `CANON`, `CANON_ADMIN`, `STRUCTURED`, `STRUCTURED_ADMIN`. Named runtime pools default to two connections and control pools to one; overflow defaults to zero. Explicit global native pool fields in a configuration file are inherited by named sources unless overridden. A product `KOINON_DATABASE_*` alias applies to primary only. Driver connection and command timeouts are bounded separately by `<SOURCE>_CONNECT_TIMEOUT` and `<SOURCE>_COMMAND_TIMEOUT` for asyncpg; defaults are 5 and 30 seconds. `KOINON_DATABASE_HEALTH_TIMEOUT` bounds the native health probe between 0.1 and 10 seconds.

With default five-source pools, one process permits eleven pooled connections and no overflow. Multiply that budget by API replicas, worker processes and deployment overlap; reserve separate capacity for identity, migrations and operators. The assistant worker runs exactly the configured number of consumer loops, with one live run per loop and no prefetch. Cancellation or an unexpected consumer failure drains peer tasks before context shutdown. The configured job lease is the default; explicit per-claim leases remain supported. Queue admission is serialized within an organization and enforces the active-answer cap per canonical owner across conversations; idempotent replay reuses its prior admission. Raising worker concurrency does not increase database capacity. Shared SQL sessions and concurrency state use the same native primary datasource; no second pool is constructed for diagnostics.

Document storage aliases are `KOINON_DOCUMENT_STORAGE_BACKEND`, `ROOT`, `S3_BUCKET`, `S3_PREFIX`, `S3_ENDPOINT_URL`, `S3_REGION` with the same prefix, plus `KOINON_DOCUMENT_STORE_ORIGINALS`. Structured storage aliases are `KOINON_STRUCTURED_STORAGE_BACKEND`, `ROOT` and `PRESIGN_TTL_SECONDS`. These override only the approved storage fields in the native module settings. They cannot change database credentials. Remote endpoints require HTTPS outside explicitly configured loopback development.

Azure Blob Storage and Google Cloud Storage use the same three explicit document, structured and private-attachment profiles. The [storage guide](storage.md) lists provider fields, environment aliases, optional installation extras, credential resolution and bounded query scratch behavior. Valid configuration and an installed SDK are separate from verified provider availability. Storage profiles are deployment configuration; organization chat settings and user API tokens cannot change them.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
