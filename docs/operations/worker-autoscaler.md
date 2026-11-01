# Counts-only PostgreSQL worker autoscaling

The fixed query is `SELECT koinon_operations.worker_demand_v1()`. It returns one nonnegative integer: ready plus active demand across the same ten specifications used by `WorkerBacklog.snapshot()`. Every queue is capped at 100,000 observations, so the aggregate is at most 1,000,000. The function uses the database clock on every query. It returns no job identifiers, source bytes, prompts, addresses or credentials. Query failures remain errors, never an invented zero.

Keep at least one worker: periodic retention, reconciliation and some exhausted-attempt cleanup in the older queues are maintenance outside this demand contract. Active demand does not prevent a platform from selecting a busy replica for removal; native drain and lease fencing remain necessary. This contract is source-qualified separately from a managed deployment or capacity measurement.

## Install after migrations

Use `deploy/provision_worker_scaler.py` from the matching verified source release, with the matching installed backend and document/structured packages. This is a separate operator action, not a product migration or a routine runtime/CI permission. Apply all current native migrations first, including communications and bulk tables.

Supply the five existing role-specific URLs through `KOINON_DATABASE_URL`, `KOINON_CANON_DATABASE_URL`, `KOINON_CANON_ADMIN_DATABASE_URL`, `KOINON_STRUCTURED_DATABASE_URL`, and `KOINON_STRUCTURED_ADMIN_DATABASE_URL`. Supply the separate installer identity through `KOINON_SCALER_OPERATOR_DATABASE_URL`. All six must resolve to the same PostgreSQL hostname, port, database and native `public` schema. The preflight rejects split-database URLs before opening a connection; it does not resolve DNS aliases or prove network access.

Provision a dedicated scaler login and its secret independently. It must have no administrative flags, memberships, or direct table/column privileges. The installer creates a separate NOLOGIN function owner with no administrative flags. Only the installing operator may have membership in that owner role; the operator requires authority to create/replace the function, transfer ownership, grant its exact columns, and manage the native tables' RLS policies. Do not give owner membership to runtime, migration or scaler identities. The `koinon_operations` schema remains operator-owned.

Pass the **effective** document and structured lease/attempt settings, rather than assuming these example values match an installation:

```bash
python deploy/provision_worker_scaler.py \
  --owner koinon_demand_owner --reader koinon_demand_reader \
  --document-lease-seconds 600 --document-max-attempts 3 \
  --structured-lease-seconds 1800 --structured-max-attempts 3
```

Without `--apply`, the command prints only fixed generated function SQL and never connects. Review it, then repeat with `--apply`. Installation is atomic and repeatable; a privilege or ownership conflict aborts the transaction. Reapply after a product upgrade or changing these native lease/attempt settings. Retain the reported contract SHA-256 with release and configuration evidence.

The function has a fixed `pg_catalog` search path and fully qualified native tables. Its NOLOGIN owner receives only the columns needed for eligibility and counts. On RLS-enabled tables, a dedicated SELECT policy permits that owner to observe demand across organizations. The scaler receives schema USAGE and function EXECUTE, with no raw-row access. PUBLIC receives no function permission. The scaler login has a five-second statement timeout. Credentials, creation and rotation remain operator-managed; no connection string belongs in a scale-rule query, command-line argument, source artifact or log.

## Connect a scaler

For an eligible KEDA PostgreSQL rule, configure its connection using a secret reference containing only the dedicated scaler login URL. Use exactly `SELECT koinon_operations.worker_demand_v1()` as the query and a positive target chosen from measured throughput. Set explicit worker minimum/maximum replicas, cooldown and polling bounds. Bound rollout overlap and maximum demand against regional CPU/memory quotas, database connection pools and provider limits. Keep HTTP scaling separate for API replicas.

A source-level count test does not establish network reachability from a managed control plane. Verify the deployed scaler can reach the private PostgreSQL endpoint, authenticate with the dedicated login, execute the fixed function, and cannot read native tables. Observe queued, retry, active, canceled and expired work during scale-out and graceful scale-in before declaring deployment acceptance.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
