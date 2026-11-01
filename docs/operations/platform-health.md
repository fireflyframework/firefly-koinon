<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Inspect platform health and system information

Platform health provides passive operational observations for the current organization. It separates observed checks from declared configuration and unavailable evidence. Refreshing the page does not send email, invoke a model, upload a file or test storage by writing an object.

Open the account menu, choose **Settings**, then select **Platform health** under **Operations**. On a small screen, use the Settings section selector. The **Health** tab shows separate counts for checks needing attention, checks not performed or expired, checks passed and components not enabled. These are counts of the returned checks, rather than a declaration that the whole installation is healthy.

Choose a service row to inspect its reason, evidence basis, observation validity and coverage. **Observed records** describes a bounded sample. A partial sample does not establish an organization-wide total. **Refresh observations** performs a fresh read; an existing settings destination appears only when the current user can open it.

## Authority

Both reads require a current organization-wide administrator membership and `catalog:read` plus `audit:read`. A workspace administrator does not qualify. Personal tokens must carry both scopes and have no workspace, asset or resource restriction. The service rechecks current primary-store authority before returning its result. Revocation committed before that final policy snapshot is checked; this does not promise physical response linearization against a concurrent change after the snapshot begins.

The same operations are available through bearer-authenticated API routes and browser-session BFF routes. The BFF uses the signed-in session, rather than accepting a bearer fallback.

| Read | Canonical path |
| --- | --- |
| Health | `GET /api/v1/tenants/{tenant_id}/platform/health` |
| System information | `GET /api/v1/tenants/{tenant_id}/platform/system-information` |

The two MCP tools, `koinon_platform_health` and `koinon_system_information`, use this same authority. They are listed only for a freshly verified organization-wide administrator PAT with both scopes. `audit:read` is accepted for these PAT reads, but is not advertised or accepted as an OAuth-requestable scope. Workspace-bound OAuth connections cannot use them and do not receive a request to expand consent. Ordinary knowledge tools retain their existing discovery behavior.

## Read the evidence

A **passed** check requires a current, time-bounded observation. Configuration alone does not establish working storage, a reachable model or successful email delivery. Observations expire after 30 seconds; consumers should treat expired passes as stale until refreshed.

Database checks reuse native connection and runtime-role observations. Index checks require a current active target in every observed workspace, matching the native active pointer and status, qualified physical index, dimensions and chunk/vector coverage. Retired history does not satisfy or invalidate a valid current serving target. Ready targets without activation, and queued or building targets, remain incomplete. Ingestion checks report bounded native job states; intentionally cancelled jobs are not counted as platform failures, and historical successful jobs do not establish that a worker is alive. Worker liveness stays unknown when no retained heartbeat evidence exists.

The reader admits at most 100 index targets and 32 native workspace bindings per domain, and returns at most 1,000 ingestion or fallback catalog status records. Reaching a bound marks coverage partial or unavailable. Individual native reads have cooperative timeouts and the complete operation has a cooperative six-second timeout. An unavailable observation contains a safe reason code; raw SQL errors, provider responses and credentials are excluded.

## System information

The **System information** tab lists six known installed distributions, the logical serving role, declared capabilities and validated limits. Process limits apply separately to each replica; file limits apply to individual files. A configured capability is not a successful health check.

Only allowlisted installed license, notice and SBOM artifacts are inspected, with a 64 KiB limit per file. **Included** means the installed artifact was read and its SHA-256 is provided. **Not provided** means a known license or notice artifact was absent. **Unknown** means presence could not be established; an absent SBOM remains unknown. The page does not invent download links or infer trusted build provenance from environment variables. A missing trusted build revision remains empty.

These reads do not expose configuration dumps, datasource URLs, paths, keys, request contents or personal records. They also do not prove external client acceptance or a completed live ingestion and retrieval journey. Use the [qualification guide](qualification.md) to record those separate checks.

## Typed clients

Python exposes `platform_health(tenant_id)` and `system_information(tenant_id)` on `KoinonClient`. Java exposes `client.platformHealth(tenantId).health()` and `.systemInformation()`, with asynchronous counterparts. TypeScript keeps this feature in a separate entrypoint:

```typescript
import { createPlatformHealthApi } from "@fireflyframework/koinon-sdk/platform-health";

const platform = createPlatformHealthApi(transport);
const health = await platform.health(tenantId, { signal: controller.signal });
const information = await platform.systemInformation(tenantId);
```

Pass the existing authenticated `KoinonTransport`. Preserve unknown values and coverage in downstream displays. See the [generated API reference](../reference/api/platform.md) for complete response fields, and the [SDK connection guide](../guides/headless.md) for connection ownership.
