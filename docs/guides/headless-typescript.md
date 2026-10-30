<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# TypeScript: use koinon without Angular

`@fireflyframework/koinon-sdk` is framework-neutral. It works with standard fetch, Blob and File APIs in Node.js 22 or later, or with your own typed `KoinonTransport`. It does not require Angular, manage routes or store user credentials.

## Install a qualified package

Install a verified package supplied by your operator:

```bash
npm install "$KOINON_SDK_PACKAGE"
```

`KOINON_SDK_PACKAGE` is a local verified `.tgz` path. Source development can build the repository's `sdk/typescript` package. The development version is not assumed to be published to npm. Source, packed-consumer, publication and live API checks are distinct.

## Connect with host-owned authentication

Set `KOINON_API_URL` to your API root ending in `/api/v1`, `KOINON_TOKEN` to a scoped personal or API-audience OIDC access token, and the tenant/workspace variables to admitted IDs. Keep credentials in a secret manager or process environment. A provider key or OIDC ID token is not an API access token.

Save this as `headless.mts`. Compile in a strict TypeScript project with NodeNext module resolution, Node types and the DOM library, then run the emitted module. Its entry point only reads context and documents:

```typescript
import {env} from 'node:process';
import {FetchTransport, KoinonClient, offsetPages} from '@fireflyframework/koinon-sdk';

function required(name: string): string {
  const value = env[name];
  if (!value) throw new Error(`Set ${name} before running this example`);
  return value;
}

export function connect(): KoinonClient {
  return new KoinonClient({transport: new FetchTransport({
    baseUrl: required('KOINON_API_URL'), accessToken: () => required('KOINON_TOKEN'),
    credentials: 'omit',
  })});
}

export async function browse(client: KoinonClient, tenant: string, workspace: string) {
  for await (const page of offsetPages(number => client.catalog.list(tenant, {
    workspace_id: workspace, kind: 'document', page: number, page_size: 25,
    sort: 'name', order: 'asc',
  }))) {
    for (const document of page.items) console.log(document.id, document.name);
  }
}

async function main() {
  const client = connect();
  const tenant = required('KOINON_TENANT_ID');
  const context = await client.context();
  if (!context.tenants.some(item => item.id === tenant)) {
    throw new Error('The selected organization is unavailable');
  }
  await browse(client, tenant, required('KOINON_WORKSPACE_ID'));
}

await main();
```

The bearer callback is evaluated for each request and may return a promise. Replace the environment lookup with the host's renewal function for expiring tokens. The fetch transport has no background client session or close method. The caller owns abort signals and any asynchronous iterator it starts.

Effective access is the intersection of selected scopes, current owner roles and credential resource bounds. A workspace/tenant selector grants no access. `catalog:read`, search, SQL, chat, ingestion and management have distinct requirements; ordinary-identity-only operations cannot be enabled with a PAT scope. See [API permissions](api-permissions.md).

For a browser session hosted by koinon, use `/bff/api/v1`, included credentials and a callback supplying the freshly decoded `XSRF-TOKEN` cookie as `X-XSRF-TOKEN` on writes. Do not combine bearer authority with BFF cookies. Your host owns cookie access, login and CORS configuration; the SDK does not read cookies itself. Server integrations use the bearer `/api/v1` API with `credentials: 'omit'` as above.

## Continue by workflow

| Workflow | Guide |
| --- | --- |
| Catalog creation, bounded uploads, search/SQL, exact document/table history and curated confirmation | [Knowledge lifecycle](typescript-knowledge.md) |
| Saved threads, scoped runs, SSE, abort versus durable cancellation and audit | [Conversations and evidence](typescript-conversations.md) |
| Providers/agents/indexes/jobs, organization directory, revisions, errors and private binaries | [Administration](typescript-administration.md) |
| Agentic execution, embeddings, RAG and RLM responsibilities | [Knowledge runtime](../concepts/knowledge-runtime.md) |
| All typed request/response signatures | [Generated API and SDK reference](../reference/sdk-api.md) |

The SDK rejects redirects and performs no automatic write retries or stream reconnection. A type check or fake-transport test proves a local contract, not configured provider availability, completed ingestion or a live model result.
