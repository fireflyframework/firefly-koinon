# Operator configuration and observations

Set `KOINON_CONFIG_FILE` to a native YAML, TOML or JSON configuration file. Only the `koinon` and `pyfly` roots are read by the service entry point. Explicit product environment aliases override matching file fields; an absent alias preserves the configured file value, including identity endpoints, client secrets, false booleans and storage paths. Native configuration placeholders can resolve externally supplied environment values. Start from `deploy/production/configuration.yaml.example`; it contains no usable credentials.

Runtime DDL and automatic runtime migrations are prohibited. The service accepts schema policy `validate` or `none`; run the separate migration job before serving traffic. A runtime service must never receive the migration URL. Each named datasource is explicit: primary, document runtime/control, and structured runtime/control. Runtime roles must have neither superuser nor row-security bypass. Control roles have narrowly granted provisioning authority; they are not application request authority.

The authorized tenant configuration response includes a read-only `deployment` descriptor. Changing tenant model providers does not change deployment storage, datasource credentials or worker limits. Operator observations contain no connection URLs, credentials, filesystem paths or raw database errors. `available: null` means unverified or unknown; it must not render as ready. Every observation includes its timestamp and reason. A configured cloud bucket or registered model is insufficient evidence of availability.

In **Storage & indexing**, **Checked** labels when the descriptor was observed. It is not proof that every row ran a live probe. A cloud storage row can legitimately show a recent timestamp together with **Not checked**: the server read its configuration but did not contact the provider. Interpret the timestamp with `available` and the reason, rather than treating recency as success. The separate [Platform health](platform-health.md) page explicitly distinguishes configuration basis, observed basis, freshness and coverage.

Database observations use the existing native DataSourceRegistry and SQLAlchemy health indicator. Pool exhaustion preserves native `UNKNOWN` even when the aggregate status is `UP`. The role check verifies role flags, not all tenant policies; qualify actual tenant isolation separately. Pool usage reflects the current application process. Native metric registration does not prove an exporter is collecting data. The public `/ready` response remains small and requires a real catalog database query; `/health` reports process liveness.

Local storage observations use the settings already bound to the document and structured modules. The service creates one random probe file in an existing root, writes, flushes, reads and deletes only that file. It never creates a missing storage root. Results are cached for 20 seconds, and at most two local probes remain in flight; slow probes report unknown. Cloud storage is never contacted automatically. Mount and provision shared storage before starting replicas, and separately qualify provider permissions, encryption and recovery.

Vector observations use only the tenant's persisted workspace bindings under the native document tenant context, with explicit tenant/workspace predicates. They check the vector extension, embedding-set completion and physical valid/ready HNSW indexes. An empty binding, missing index, interrupted embedding set or exceeded verification limit cannot produce ready. Index creation belongs to privileged migrations or reviewed control operations, never runtime DDL.

## Browser session expiry and renewal

When the configured native session store supports expiry observations, management
shows a small warning during the last two minutes of the observed session lifetime.
It displays the remaining time and **Renew session**, including inside an open
Library dialog. Unknown expiry stays unknown: an older framework or a custom store
without the capability produces no invented countdown.

1. Choose **Renew session** to open the existing sign-in flow in a separate window.
   Allow the sign-in pop-up if your browser blocks it. The original page stays open.
   No sign-in is started automatically by the countdown or its read-only checks.
2. Complete your identity provider's normal sign-in requirements. The application
   waits for an observed completed login, then checks the same canonical account
   and fresh permissions. Starting OAuth alone is not completion, even when saving
   OAuth state changes the session deadline.
3. Continue only with current access. Before expiry, mounted form edits remain in
   the original page. After a denied/expired request, bounded Library create/edit
   text can be restored in this tab for the same account and still-authorized
   destination. Changed account, lost permissions, changed edited entry or logout
   discards that recovery. Other forms and selected file contents are not covered
   by this text recovery; save or copy those edits before signing in again.

No write, upload or failed request is replayed by renewal. If a request was already
in flight, inspect Library or Activity before manually submitting again. A network
failure can leave its outcome unknown. Drafts are kept only in tab memory, not in
URLs, local storage or session storage, and a full reload does not restore them.

Authenticated browser `GET /auth/me` returns additive `expires_at`,
`authenticated_at` and `server_time` observations with `Cache-Control: no-store`.
It never returns a session ID, cookie, token or session attributes. A bearer
principal does not receive a matching cookie's expiry. These browser observations
are separate from the personal-token and MCP OAuth lifetimes in the headless SDKs.
Subsequent requests always run normal authentication and authorization checks.

`pyfly.session.ttl` is the native store lifetime in seconds, default `1800`.
It applies when a session is saved, replaced or renamed; reading expiry does not
renew it. A reissued cookie's `Max-Age` and `HttpSession.last_accessed` are not
authoritative remaining lifetime. There is no new idle or hard timeout policy,
refresh-token grant, membership extension or identity-provider policy change in
this UI. Keep the deployment's reviewed lifetime and secure cookie configuration.

## PostgreSQL TLS by driver

Choose the driver before preparing connection options. PyFly passes `connect-args` to that driver without translating TLS fields. A different database role can use the same driver; elevated credentials do not require switching drivers.

### Runtime profiles using asyncpg

1. Use `postgresql+asyncpg://` in each of the five runtime URLs. Keep each role's credentials in the protected environment or secret manager.
2. Mount the reviewed CA bundle read-only in the process or container. For the boolean TLS configuration below, set `SSL_CERT_FILE` to that readable PEM bundle before starting Python. This affects Python's default TLS trust, so the bundle must also contain any roots required by other default-context clients in that process.
3. Enable strict TLS in the native profile:

```yaml
pyfly:
  data:
    relational:
      url: ${KOINON_DATABASE_URL}
      connect-args:
        ssl: true
      datasources:
        canon:
          url: ${KOINON_CANON_DATABASE_URL}
        canon_admin:
          url: ${KOINON_CANON_ADMIN_DATABASE_URL}
        structured:
          url: ${KOINON_STRUCTURED_DATABASE_URL}
        structured_admin:
          url: ${KOINON_STRUCTURED_ADMIN_DATABASE_URL}
```

For asyncpg, `ssl: true` creates Python's default SSL context with certificate and hostname verification enabled. Named datasources inherit these connect arguments when they use the same driver. A named override must preserve the intended verification policy. Do not disable hostname checks to make a database IP address work; use the certificate's DNS name.

An alternative is an SQLAlchemy/asyncpg URL with `?ssl=verify-full` and a readable `PGSSLROOTCERT` PEM path. This is a separate CA-loading path: `PGSSLROOTCERT` supplies asyncpg's named SSL mode, while the boolean `ssl: true` path uses Python's default trust configuration. Choose one approach and verify the actual effective connection settings. See the [asyncpg connection reference](https://magicstack.github.io/asyncpg/current/api/index.html#asyncpg.connection.connect).

### Migration and backup profiles using psycopg and libpq

The separate migration command uses psycopg. Configure its operator-only `KOINON_MIGRATION_DATABASE_URL` with `sslmode=verify-full` and `sslrootcert`, for example this URL structure with placeholders:

```text
postgresql+psycopg://ROLE:PASSWORD@DATABASE_HOST:5432/DATABASE?sslmode=verify-full&sslrootcert=/etc/koinon/certs/database-ca.pem
```

Replace and URL-encode the credential components in a protected file; do not print the completed URL. The CA file must exist inside the migration container. Backup tooling reads the same libpq TLS fields. Neither accepts asyncpg's `ssl` keyword. The [PostgreSQL connection parameters](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS) define these fields; [migration instructions](migrations.md) keep the operator credential separate from runtime processes.

### Bootstrap with an application context

Bootstrap and other operator commands that construct Koinon's application context use its runtime datasource configuration. Prepare a separate protected operator environment with the necessary primary role, but retain the runtime driver and matching TLS options. For the asyncpg profile above, keep `KOINON_DATABASE_URL` as `postgresql+asyncpg://...`; do not replace it with `KOINON_MIGRATION_DATABASE_URL`. A psycopg URL combined with the inherited asyncpg `ssl: true` field fails before it can connect. Preserve the four named datasource profiles and their role boundaries as well.

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

## Model output protocols

Administrators can set `model_options.output_mode` on an agent or a separate generative knowledge connection. The shared advanced model options show **Auto**, **Default structured output** (`default`) and **Native JSON** (`native`). Omitted or null preserves existing behavior: native output for Ollama bindings and the SDK default for other providers. This option does not change the outer chat answer from text to JSON.

An explicit `default` uses the model profile's normal structured-output protocol; for document RLM actions it selects function tools. An explicit `native` requests schema-constrained JSON. The runtime checks the actual resolved model profile and current capability negatives before dispatch and stops on incompatibility. It never switches protocols after a failed request. These choices do not override provider profiles or add arbitrary provider request settings.

A `current_agent` knowledge role inherits its admitted agent's effective mode. It cannot override model options; embedding roles do not accept output modes. Saving an agent choice advances its revision, so an already queued answer cannot silently adopt the changed configuration. New generation receipts record the chosen `binding_output_mode` and normalized `model_options_sha256`; missing historical values remain unknown. A binding mode is not proof of the actual wire protocol or a successful RLM answer.

Provider discovery and advertised tools support remain separate from observed generation and semantic qualification. Selecting a protocol does not qualify curated RLM, bypass recorded-view/read guards, or alter model, iteration, token or execution budgets.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
