<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# TypeScript: use koinon without Angular

`@fireflyframework/koinon-sdk` is framework-neutral. It works with standard fetch, Blob and File APIs in Node.js 22 or later, or with your own typed `KoinonTransport`. It does not require Angular, manage routes or store user credentials.

## Work through the tutorial

Start here when you have an API address and an account but have not written an integration yet. The first program establishes authentication, checks the available organization context, and pages through documents. It makes no changes. After it works, keep the same client configuration for [knowledge](typescript-knowledge.md), [conversations](typescript-conversations.md), and [administration](typescript-administration.md).

Use the resource IDs from your first catalog read in the remaining chapters. Each chapter introduces the permissions, inputs and response fields needed for its operations.

[Download the complete TypeScript tutorial source and build instructions](../examples/typescript/README.md). The files include imports and entry points. Each chapter's default entry point reads existing state; write helpers are separate functions that your application calls after its own explicit decision. Keep all files for the selected language together.

## Prepare the deployment and credential

Ask your operator for an authorized API root, an organization, and a workspace you can read. Start with a credential whose scope includes `catalog:read` and whose resource bounds admit that workspace. Do not request every management scope merely to make the first request succeed.

| Value | Where it comes from | How the program uses it |
| --- | --- | --- |
| `KOINON_API_URL` | Your deployment operator | API root ending in `/api/v1`, without a token in the URL. |
| `KOINON_TOKEN` | A current API-audience OIDC access token or a scoped personal API token | The callback supplies it afresh for each request. |
| `KOINON_TENANT_ID` | The organization's canonical ID in the current context | Every tenant operation uses this exact organization. |
| `KOINON_WORKSPACE_ID` | An authorized workspace returned by the API | Catalog and knowledge filters stay inside this destination. |

An OIDC access token comes from your host's approved identity flow. This tutorial does not implement that flow or ask for a refresh token. For a personal token, sign in through the ordinary account flow, review its permitted scopes and resource bounds, and save its one-time secret privately. An existing PAT cannot create another PAT. Never substitute a model-provider key, an ID token, or an MCP resource token.

Set the variables through your shell's secure environment mechanism or secret manager. Avoid pasting live credentials into an example file, a terminal transcript, a URL, or a support ticket. A long-running host should renew its access token before returning it from the callback; replacing an expired token is the host's responsibility.

## Install the SDK

Install a verified package supplied by your operator:

```bash
npm install "$KOINON_SDK_PACKAGE"
```

Download the SDK `.tgz` archive and `SHA256SUMS` from [GitHub Releases](https://github.com/fireflyframework/firefly-koinon/releases), verify its checksum, and set `KOINON_SDK_PACKAGE` to the local archive path. For source development, build the repository's `sdk/typescript` package.

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

## Understand the first response

Run the startup program only after choosing the deployment and credential above. The context response identifies the current subject, available organizations, memberships, workspaces, and applicable permissions. Select IDs from that response rather than displaying a guessed organization or treating a URL parameter as a grant. In an application, keep that context with the authenticated session and discard it when the identity changes.

The catalog request returns a typed page. `items` contains the current authorized rows; `page`, `page_size` or `size`, `pages`, and `total` describe pagination when the endpoint supplies them. The helper asks for another server page lazily. It does not fetch a large list and slice it locally. An empty list can be a legitimate empty scope; it is not an invitation to remove the workspace filter.

The printed IDs and names are the program's expected output. They are resource identities for later calls, not sample fixture IDs you should hardcode. Retain a selected document or dataset ID when moving to the next chapter. Keep names as labels, since renaming an asset does not change its identity.

If the first call returns `401`, repair the host's token acquisition or expiry handling before continuing. If it returns `403`, compare the current role, requested scopes, resource bounds, and credential type. A wider token cannot repair a missing role. For a timeout or protocol error, retain only safe status and request-reference metadata; never print the token or a whole private response body.

The SDK does not renew credentials, create a sign-in session, or reconnect a stream automatically. Keeping those responsibilities in the host lets a web application, command-line tool, and scheduled service use the same API without sharing browser cookies or credentials accidentally.

## Continue by workflow

| Workflow | Guide |
| --- | --- |
| Catalog creation, bounded uploads, search/SQL, exact document/table history and curated confirmation | [Knowledge lifecycle](typescript-knowledge.md) |
| Saved threads, scoped runs, SSE, abort versus durable cancellation and audit | [Conversations and evidence](typescript-conversations.md) |
| Providers/agents/indexes/jobs, organization directory, revisions, errors and private binaries | [Administration](typescript-administration.md) |
| Agentic execution, embeddings, RAG and RLM responsibilities | [Knowledge runtime](../concepts/knowledge-runtime.md) |
| All typed request/response signatures | [Generated API and SDK reference](../reference/sdk-api.md) |

Use the operation's saved state and request identity to reconcile an interrupted write or event stream.
