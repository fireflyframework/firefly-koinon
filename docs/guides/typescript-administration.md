<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# TypeScript: administration and safe client operations

Start with the [standalone client](headless-typescript.md). Organization management requires organization-scoped authority. Token scopes intersect with the owner's current roles and resource bounds; a workspace administrator cannot turn a scoped token into an organization grant. The [permission guide](api-permissions.md) lists role and scope dependencies.

## Choose the management group

| Task | TypeScript group | Boundary |
| --- | --- | --- |
| Model providers and agents | `providers`, `agents`, `configuration` | `providers:write`/`agents:write`; discovery, validation and successful chat/tool execution are separate observations. |
| Source connections and roles | `knowledgeConnections` | `sources:configure`; explicit tenant defaults/workspace assignments and current revisions. |
| Embeddings/index lifecycle | `knowledgeIndexes.plan/create/get/activate/cancel/resume` | `indexes:manage`; review plans, expected active connection/index state and durable job outcomes. |
| Durable jobs | `jobs.list/get/cancel` | `jobs:manage` plus current resource authority; items-only lists are not synthetic pages. |
| Access and activity | `members`, `invitations`, `audit` | Appropriate current scope and `members:write`/`audit:read`. |
| Personal account | `profile`, `tokens` | The authenticated account; token creation/revocation requires a verified ordinary identity. |
| Organization defaults | `organizationChat`, `organizationKnowledge`, `branding` | Endpoint-specific management permissions and expected revisions. |

The client does not provision deployment adapters, configure model credentials, install embeddings or start workers. Provider/connection availability is a server observation. Read the [knowledge runtime guide](../concepts/knowledge-runtime.md) before selecting retrieval/agent/index workflows. Keep credentials in the server's supported configuration and out of chat input and logs.

Corporate identity provider administration, directory group discovery, group-to-role mappings, corporate profile mappings and OAuth client registration require an ordinary verified identity. PAT/application credentials cannot bypass these gates by requesting `identity:manage`. MCP resource credentials are separate from API bearer credentials; see [application registration](register-applications.md).

## Plan embedding work explicitly

Choose an admitted provider/model and the intended workspace. The helper requests server plan/validation, without creating or activating an index:

```typescript
import {KoinonClient} from '@fireflyframework/koinon-sdk';

export async function planEmbeddings(
  client: KoinonClient, tenant: string, workspace: string, providerId: string, modelId: string,
) {
  return client.knowledgeIndexes.plan(tenant,
    {workspace_id: workspace, domain: 'documents', provider_id: providerId, model_id: modelId});
}
```

Review the plan before explicit `knowledgeIndexes.create`. Create/resume uses a stable idempotency key; activation is separate and carries current revision, active-index and connection-revision preconditions. Inspect the durable job outcome before switching serving state. Typed configuration or a plan does not prove successful provider/embedding execution. See [knowledge runtime](../concepts/knowledge-runtime.md) for lexical retrieval, embedding indexes and active serving configuration.

## Keep null, omission and revisions distinct

Omit a property to preserve it; use explicit `null` only where clearing is supported. `false` and zero remain real values. Read the current state before building a revisioned update:

```typescript
import {KoinonClient} from '@fireflyframework/koinon-sdk';

export async function clearManager(client: KoinonClient, tenant: string, personId: string) {
  const current = await client.organizationPeople.get(tenant, personId);
  if (current.revision === undefined) throw new Error('Current revision is required');
  return client.organizationPeople.update(tenant, personId,
    {expected_revision: current.revision, manager_id: null});
}

export async function clearDefaultAgent(client: KoinonClient, tenant: string) {
  const current = await client.organizationChat.get(tenant);
  return client.organizationChat.update(tenant,
    {expected_revision: current.revision, default_agent_id: null});
}
```

These are writes requiring organization-level `members:write` and `agents:write`, respectively. A managed source is released with `manage_locally: true`, not a null provider ID. Reattachment uses explicit `managed_provider_id`, both member/identity management permissions and an active enabled mapping. It preserves values until a verified source observation. Position updates never change access roles.

`organizationPeople.me/list/units/reports` use the appropriate self/current visibility rules. Shared-workspace reads require `workspace_id`; asset-restricted tokens cannot browse this directory. Avatars use the returned assignment or visible profile ID. Clear scoped rows and revoke object URLs after user/client/permission changes or a server denial. Guard asynchronous response application against the same context and selected entity so old results cannot overwrite a new tenant or provider. See [people and organization](people-and-organization.md).

## Page lazily and cancel owned requests

```typescript
import {KoinonClient, offsetPages} from '@fireflyframework/koinon-sdk';

export async function browseDocuments(
  client: KoinonClient, tenant: string, workspace: string, signal: AbortSignal,
) {
  for await (const page of offsetPages((number, currentSignal) =>
    client.catalog.list(tenant,
      {workspace_id: workspace, kind: 'document', page: number, page_size: 25},
      {signal: currentSignal}), 1, signal)) {
    for (const document of page.items) console.log(document.id, document.name);
  }
}
```

The caller owns `AbortController`; pass its signal through the request options. Page helpers fetch lazily without prefetch or client-side slicing, stop on inconsistent paging, and do not invent pages for items-only endpoints. Use `cursorPages` only for cursor-based APIs. Organization/history pages have their own typed envelopes; inspect their `page`/`pages`/`has_next` metadata explicitly. Aborting HTTP is distinct from canceling a durable server job or run.

## Treat errors and binary data explicitly

```typescript
import {KoinonClient, KoinonError} from '@fireflyframework/koinon-sdk';

export async function readEntry(client: KoinonClient, tenant: string, entryId: string) {
  try {
    return await client.catalog.get(tenant, entryId);
  } catch (error) {
    if (error instanceof KoinonError) {
      console.error(error.status, error.code, error.requestId);
    }
    throw error;
  }
}
```

On `401`, renew through the host identity flow or require sign-in. On `403`, discard the denied scoped data and recheck current roles/token bounds. A revision/content conflict requires reloading and a new reviewed decision. Validation failures require corrected input. A timeout, disconnected write or typed `pending` outcome requires reconciliation with the original request/idempotency identity, not an automatic new write. Redirects are rejected, and the SDK does not automatically retry writes.

`documents.download`, `documents.versionOriginal` and avatar helpers return `BinaryDownload` with a Blob and nullable metadata. Do not use a server filename as an unchecked local path. Treat `not_modified` separately from new bytes, do not share cache entries between users, and revoke any object URL when its authorized view ends. The [generated API reference](../reference/sdk-api.md) supplies every request, response and method signature.
