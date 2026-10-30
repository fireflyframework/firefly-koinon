<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# koinon TypeScript SDK

A framework-neutral typed client for the koinon API. It works with standard fetch, Blob and File APIs in Node.js 22 or later, or with a host-supplied `KoinonTransport`. It does not require Angular, manage routing, read cookies or store user credentials.

## Install and read

Install an operator-supplied verified package with `npm install "$KOINON_SDK_PACKAGE"`, where the variable names a local `.tgz`. Source development builds `sdk/typescript` from the repository. A packed-consumer check does not imply npm publication or live API acceptance.

Set the API URL ending in `/api/v1`, a scoped token and an authorized tenant ID in the environment. Compile this module with strict NodeNext resolution, Node types and the DOM library. It reads only:

```typescript
import {env} from 'node:process';
import {KoinonClient, FetchTransport} from '@fireflyframework/koinon-sdk';

function required(name: string): string {
  const value = env[name];
  if (!value) throw new Error(`Set ${name}`);
  return value;
}

const client = new KoinonClient({transport: new FetchTransport({
  baseUrl: required('KOINON_API_URL'), accessToken: () => required('KOINON_TOKEN'),
  credentials: 'omit',
})});
const tenant = required('KOINON_TENANT_ID');
const context = await client.context();
if (!context.tenants.some(item => item.id === tenant)) {
  throw new Error('The selected organization is unavailable');
}
const documents = await client.catalog.list(tenant, {kind: 'document', page: 1, page_size: 25});
for (const document of documents.items) console.log(document.id, document.name);
```

The bearer callback is evaluated per request and can return a promise. Supply a personal token or an API-audience OIDC access token; renewal belongs to the host. For BFF browser sessions use `/bff/api/v1`, included credentials and a freshly decoded CSRF cookie callback. Do not send bearer credentials to the BFF. The host supplies cookie access and login. `FetchTransport` has no background session or client-close method; the caller owns abort signals and asynchronous iterators.

## Follow a workflow

These links target guides in the source repository:

- [TypeScript setup, authentication and first read](../../docs/guides/headless-typescript.md)
- [Knowledge creation, intake, search/SQL, exact history and curated confirmation](../../docs/guides/typescript-knowledge.md)
- [Conversations, SSE, cancellation, audit and reviewed exports/proposals](../../docs/guides/typescript-conversations.md)
- [Administration, organization directory, paging, revisions, errors and private downloads](../../docs/guides/typescript-administration.md)
- [Agentic, embedding, RAG and RLM responsibilities](../../docs/concepts/knowledge-runtime.md)
- [Generated API reference](../../docs/reference/sdk-api.md)

| Capability | Client group |
| --- | --- |
| Catalog and ingestion | `catalog`, `sources`, `dataset.appendFile` |
| Search and structured evidence | `search`, `query`, `dataset` schema/snapshot/provenance/coordinate methods, `structured.glossary`/`agentGlossary` |
| Immutable document history | `documents.versions/version/extractions/parts/part/versionOriginal` |
| Content changes | `documents.replace/reingest`, `dataset.replaceTable/reingestTable` with current digest/snapshot preconditions |
| Curated knowledge | `knowledgeIntents.preview/get/confirm/cancel`, `knowledgeItems.list/get/version` |
| Conversations and private attachments | `chat` threads, folders, runs/events/results/audit/activities, proposals and attachments |
| Model and source operations | `configuration`, `providers`, `agents`, `knowledgeConnections`, `knowledgeIndexes`, `jobs` |
| Organization and account | `organizationPeople`, `members`, `invitations`, `audit`, `profile`, `tokens`, `branding`, `organizationChat`, `organizationKnowledge` |
| Reviewed distribution | `exports`, `shares`, `evidence` |
| Connected applications | `authorizedApplications`, `mcp`, `mcpOAuthClients`, `externalReviews`, `externalFileReviews` |

Use the checked `sdk/contract/operations.json` and `schemas.json` for current signatures and counts. Qualified retained glossary operations are listed separately; operator probes and browser-only authentication routes are excluded from the headless contract.

## Preserve authority, cancellation and exact data

- Scopes intersect with the owner's current roles and resource bounds. Organization position changes do not grant access. Corporate mapping, OAuth registration and token administration retain ordinary verified-identity gates that PAT scopes cannot override.
- Omission preserves fields; explicit null clears only fields that support clearing. False and zero remain values. Read current revisions before updates; source release uses `manage_locally: true` rather than a null provider ID.
- Pass `AbortSignal` through request options and close partially consumed streams. Breaking or aborting SSE closes HTTP, not a durable run; use `chat.cancel` explicitly. Resume intentionally with the last fully processed event ID and handle `message_reset`.
- `offsetPages` and `cursorPages` are lazy and use server-owned paging. They never prefetch, synthesize pages for items-only lists or silently loop on inconsistent cursors.
- Redirects are rejected. Writes and SSE reconnection are not automatically retried. Retain stable idempotency/request identities and reconcile timeouts, `pending` and unresolved commits.
- `KoinonError` exposes status, code and request identity. Invalidate denied scoped data on 401/403 and keep credentials/request bodies out of logs.
- `BinaryDownload` preserves Blob/ETag/filename/content-type metadata and explicit authorized 304 state. Do not expose private downloads publicly or share caches between users. Revoke object URLs when their view ends.
- Exact decimals and unsafe integers stay strings; `exactDecimal`/`exactInteger` validate explicit conversions. Preserve immutable audit/source identities, nullable completeness and unrecorded RLM history.
- Proposals and curated/external changes require genuine reviewed confirmation. Public clients cannot fetch component-only approval nonces or invent curated delete/share/export/derive APIs.

Build and test through the package's configured scripts. Source checks, packed consumers, publication, provider/database integration and live application acceptance remain separate evidence.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0.
