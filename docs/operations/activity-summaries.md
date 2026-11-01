<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Understand activity summaries

Activity summaries describe recorded work with knowledge. They show the pieces someone created, updated or consulted, the knowledge projects involved, and separately measured MCP requests and tool executions. They contain counts and authorized project names, without questions, answers or conversation contents.

Start with a personal summary for a short period. Check its coverage before comparing it with another report. An organization administrator can also request an organization summary; this is a separate operation with a stricter permission check.

## What each number means

A piece is a document, dataset or curated knowledge item. Creating a source connection, indexing a table or splitting a document into chunks does not create additional pieces in these counts. A piece is counted once in each category for the selected period. A document created and then updated can appear in both categories. Daily figures count each piece once per local day, so adding daily figures can exceed the period's distinct-piece total.

Creation and update activity comes from committed semantic audit events. Updates include content changes and catalog name, description or metadata changes; operational status changes alone do not count. Consultations require exact recorded source receipts from knowledge queries, MCP reads or chat retrieval. An attachment used privately in a chat is not published organizational knowledge. Opening a screen without a source receipt does not establish a recorded consultation.

Only knowledge accessible under the requesting user's **current** membership and credential restrictions contributes to the response. Archived ancestry and unavailable resources are excluded. The service reads primary-store policy snapshots and checks authority again before returning the report. Removing access can change a later summary of the same historical period.

| Measurement | Meaning |
| --- | --- |
| MCP requests | Authenticated transport requests recorded by the native boundary |
| MCP tool calls | Logical tool executions, counted separately from requests |
| Tool outcomes | Completed, failed, rejected or cancelled tool observations |
| Tool duration | Measured tool execution, excluding the activity-recording write |
| Request duration | Entire HTTP request lifetime; a long-lived SSE request can last much longer than one tool |
| Provider tokens and cost | Available only when a retained provider observation supplies them |

An HTTP 200 response can contain a failed MCP tool result. The two outcomes remain separate. A tool observation's single-workspace label comes from its freshly verified credential scope; it is not a claim that a particular document was read. Unknown-workspace observations cannot be included in a report restricted to a workspace. Credentials restricted to individual assets cannot use unattributed transport counts to infer wider activity.

## Read coverage before using a count

Every measurement carries `status` and `value`. An observed zero is a recorded zero. An unavailable value is `null`; never replace it with zero. A partial value is a lower bound or an explicitly scoped subset. Reasons explain bounded history and incomplete observation coverage.

The report's coverage is separate from each number. MCP observations are best effort: recording failures must not turn a successful knowledge operation into a failed one. The observation start date does not prove that every event was captured. An unknown number of missing observations remains `null`.

Consultation coverage is limited to exact source receipts. Reports currently mark provider token and cost measurements unavailable where those records do not exist. Consumption charged by an external Claude or ChatGPT account is not visible to koinon and is not estimated as a platform cost.

History projection is bounded to 10,000 candidate rows per report. Reaching the bound marks knowledge totals partial. Shorten the period before treating a partial count as a complete total. The selected interval is inclusive at `start_at` and exclusive at `end_at`, must use timezone-aware timestamps, and cannot exceed 366 days. `time_zone` is an IANA identifier used for daily calendar boundaries.

## Choose access deliberately

Personal reports require `activity:read` and its `catalog:read` dependency. A personal report always uses the authenticated subject; there is no parameter for choosing another person. Current role, tenant, workspace and asset limits continue to apply.

Organization reports require a current organization-wide administrator membership. A scoped token must also carry `activity:read`, `catalog:read` and `audit:read`, with no workspace or asset restriction. A workspace administrator or an operator cannot request an organization-wide report by changing the request body.

The canonical read-only operations use POST so a typed interval can be passed as a JSON body:

| Operation | Path |
| --- | --- |
| Your activity | `/api/v1/tenants/{tenant_id}/activity/personal` |
| Organization activity | `/api/v1/tenants/{tenant_id}/activity/administration` |

## Python

Install the [Python SDK](../guides/headless-python.md), then provide your installation's API root and a scoped token through the environment. This complete script requests the previous seven days and preserves an unavailable value when printing it.

```python
import asyncio
import os
from datetime import UTC, datetime, timedelta

from koinon_sdk import ActivityWindow, KoinonClient


async def main():
    end = datetime.now(UTC)
    window = ActivityWindow(
        start_at=end - timedelta(days=7),
        end_at=end,
        time_zone="Europe/Madrid",
    )
    async with KoinonClient(
        os.environ["KOINON_API_URL"],
        token_provider=lambda: os.environ["KOINON_API_TOKEN"],
    ) as client:
        report = await client.personal_activity(os.environ["KOINON_TENANT_ID"], window)
        created = report.knowledge.created
        print("Pieces created:", created.value if created.value is not None else "not recorded")
        print("Measurement status:", created.status)
        print("Coverage:", report.coverage.reasons)


asyncio.run(main())
```

To read an organization report with the administrator permissions described above, call `client.administrative_activity(tenant_id, window)`. Both methods return `ActivitySummary`. Decimal provider cost, when recorded, remains an exact decimal value; do not convert it to a binary float for accounting.

## TypeScript

Use the [TypeScript SDK connection guide](../guides/headless-typescript.md) to install the package. The transport obtains the token for every request. An `AbortSignal` can cancel a report request without changing knowledge.

```typescript
import { FetchTransport, KoinonClient, type ActivityWindow } from '@fireflyframework/koinon-sdk';

async function main() {
  const transport = new FetchTransport({
    baseUrl: process.env['KOINON_API_URL']!,
    accessToken: () => process.env['KOINON_API_TOKEN'] ?? null,
    credentials: 'omit',
  });
  const client = new KoinonClient({ transport });
  const end = new Date();
  const window: ActivityWindow = {
    start_at: new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    end_at: end.toISOString(),
    time_zone: 'Europe/Madrid',
  };
  const controller = new AbortController();
  const report = await client.activity.personal(process.env['KOINON_TENANT_ID']!, window, {
    signal: controller.signal,
  });
  const created = report.knowledge.created;
  console.log('Pieces created:', created.value ?? 'not recorded');
  console.log('Measurement status:', created.status);
  console.log('Coverage:', report.coverage.reasons);
}

await main();
```

`client.activity.administrative(tenantId, window, options)` requests the stricter organization report. Both methods return a typed `ActivitySummary`. Keep optional exact-cost decimal strings intact rather than coercing them to JavaScript numbers.

## Java 21 and later

Follow the [Java SDK setup](../guides/headless-java.md) first. Resource APIs offer synchronous methods and `CompletableFuture` variants. This complete Java program uses the same interval and permission rules as the other SDKs.

```java
import java.net.URI;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.ActivityWindow;

public final class PersonalActivity {
    public static void main(String[] args) {
        var end = Instant.now();
        var window = new ActivityWindow(end.minus(7, ChronoUnit.DAYS), end, "Europe/Madrid");
        var apiRoot = URI.create(Objects.requireNonNull(System.getenv("KOINON_API_URL")));
        var tenant = Objects.requireNonNull(System.getenv("KOINON_TENANT_ID"));
        try (var client = KoinonClient.builder(apiRoot)
                .bearerToken(() -> System.getenv("KOINON_API_TOKEN")).build()) {
            var report = client.activity(tenant).personal(window);
            var created = report.knowledge().created();
            System.out.println("Pieces created: " + Objects.toString(created.value(), "not recorded"));
            System.out.println("Measurement status: " + created.status());
            System.out.println("Coverage: " + report.coverage().reasons());
        }
    }
}
```

Use `client.activity(tenant).administrative(window)` for an organization report. `personalAsync` and `administrativeAsync` provide the corresponding asynchronous operations. Recorded cost amounts use `BigDecimal`; unavailable measurements remain nullable.

## Through MCP

Authorize `activity:read` as well as `catalog:read` for the application connection. Ask `koinon_activity_summary` for the tenant and an `ActivityWindow`. This read-only tool returns your own currently authorized summary, including coverage and source-receipt-based consultation counts. It does not publish knowledge, inspect other people's private conversations, or grant organization-wide reporting access.

The application administrator must allow the scope before the owner can authorize it. Existing connections do not gain a newly added scope automatically. Use the [MCP connection guide](../guides/connect-claude.md) to review and update the connection's permitted access.
