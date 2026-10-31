<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# TypeScript: administration and safe client operations

Start with the [standalone client](headless-typescript.md). Organization management requires organization-scoped authority. Token scopes intersect with the owner's current roles and resource bounds; a workspace administrator cannot turn a scoped token into an organization grant. The [permission guide](api-permissions.md) lists role and scope dependencies.

## Work from observations to deliberate changes

Start by reading current context and selecting the organization you administer. Distinguish organization authority from workspace administration: a workspace role cannot be widened by requesting an organization-management scope. For each task, use the [permission matrix](api-permissions.md) to choose an ordinary identity or a permitted bounded API credential before constructing an input.

[Download the complete administration source](../examples/typescript/README.md). Its default entry point reads only the current account's position in the selected organization, using the self/profile boundary. Provider, member, agent, knowledge-settings and index helpers are separate operations; importing the file or constructing a client does not execute them.

For a production host, build an administrative screen or command in two stages: load and display the current state, then submit the reviewed typed change after a person chooses it. Retain the reviewed revision, operation identity and safe response metadata. Do not turn a permission failure into a request for every available scope or retry an unknown write automatically.

## Run the read-only chapter

Download `support.mts`, the selected chapter module and `tsconfig.json` together, then use the Node package from setup. [Complete source and build instructions](../examples/typescript/README.md) include [the entry-point file](../examples/typescript/administration.mts). Use the organization already selected in `KOINON_TENANT_ID`. Keep credentials in the approved environment rather than adding them to these commands.

```sh
npx tsc -p tsconfig.json
node dist/administration.mjs
```

The result prints the current tenant position ID, job title and available revision. A missing assignment can have null ID and revision zero; the GET does not create it. If authorization fails, return to the setup chapter and inspect current context/scopes instead of broadening the request. The remaining helpers define the intended mutations, but this command does not invoke them.

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

## Configure a provider and an agent in order

Read the current provider observations through configuration before creating another provider. Select a supported provider kind and API variant, the deployment-approved endpoint, and actual model IDs. Supply real credentials through your approved secret source only when the provider requires them. The typed `ProviderInput` in the complete source accepts the reviewed configuration; it does not contain a sample provider key, discover secret values, or prove connectivity. Never print the input or a one-time secret return.

Call `providers.create` only after that configuration is reviewed. Save the returned provider ID and inspect its observed availability. A separate validate operation can contact the configured external system and must be run intentionally. Successful configuration serialization is different from a successful provider test, and both are different from a completed answer.

Next build a typed agent input using that actual provider ID, a model ID available there, a chosen knowledge scope and only the tools needed for the task. The complete source's agent helper keeps these inputs explicit. Call `agents.create` with `agents:write`, retain its ID, and inspect its validation/availability. Selecting tools or an agent does not grant the agent more knowledge access than the current caller.

Finally read the organization's chat settings, display the selected default agent and revision, and update that default only after a person confirms it. Omitting a patch field preserves it; explicit null clears a field only where the endpoint permits it. Preserve unrelated settings. Re-read after a revision conflict instead of taking a new revision and silently replaying the old decision.

These complete functions keep the actual provider/model, tool scope and reviewed settings revision explicit. Your host supplies a real decision separately for each change. The returned agent or settings object records saved configuration; it does not establish that a model run succeeded.

```typescript
import {
  KoinonClient, type KnowledgeScope, type OrganizationKnowledgeSettings,
} from '@fireflyframework/koinon-sdk';

export async function createReviewedAgent(
  client: KoinonClient,
  tenant: string,
  providerId: string,
  modelId: string,
  scope: KnowledgeScope,
  personConfirmed: boolean,
) {
  if (!personConfirmed) throw new Error("Review the model, tools and scope");
  return client.agents.create(tenant, {
    name: "Knowledge reader",
    provider_id: providerId,
    model_id: modelId,
    scope,
    tools: ["search_knowledge", "inspect_schema", "query_dataset"],
    enabled: true,
  });
}

export async function setReviewedDocumentMode(
  client: KoinonClient,
  tenant: string,
  reviewed: OrganizationKnowledgeSettings,
  mode: "rag" | "rlm",
  personConfirmed: boolean,
) {
  if (!personConfirmed) throw new Error("Review the mode and retained settings");
  return client.organizationKnowledge.update(tenant, {
    expected_revision: reviewed.revision,
    documents: { ...reviewed.documents, answer_mode: mode },
    structured: reviewed.structured,
  });
}
```

## Choose RAG or RLM and plan index work

Read `organizationKnowledge.get` before changing document behavior. Copy its document and structured sections into the typed settings input, change only the chosen supported value, and send the reviewed revision. The complete source demonstrates changing document `answer_mode` while preserving all other document parameters and the structured settings. Use `settings:write` and current organization authority.

RAG retrieves an admitted evidence subset for an answer. RLM uses the configured bounded native exploration policy. Neither setting provisions a provider, changes a source connection, imports an embedding model, or proves a successful run. Inspect the [knowledge runtime prerequisites](../concepts/knowledge-runtime.md) before enabling either mode, and use the answer audit to distinguish recorded retrieval and RLM actions from missing historical metadata.

For an embedding rebuild, read available choices and call `knowledgeIndexes.plan` with the intended workspace/domain and actual provider/model IDs. Display the plan's scope and effects first. Creating with `knowledgeIndexes.create` is a separate action requiring `indexes:manage` and a stable caller-owned idempotency key. Retain the returned index/job identity and inspect `jobs.get` or the index state before assuming processing finished.

Activation is another explicit transition. Use the current revision and expected active index/connection preconditions from the reviewed state. Canceling HTTP does not cancel a server rebuild. Use its explicit cancellation operation when requested; resume requires its own current preconditions and stable request identity. A failed or pending state is not permission to discard history or invent a recovery action.

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

## Manage access separately from presentation

List members in the authorized organization/workspace and select the exact membership to change. A typed member update changes `role` or `active`; it is an access decision requiring `members:write` and current membership-management authority. Review the affected person, scope and change before sending it. A title, department, unit, reporting line or avatar is presentation data and never grants a role.

Use `organizationPeople.me` for the current tenant position and `profile.get` for the personal account. The directory has its own visibility setting and current membership guard; a shared-workspace projection does not expose the entire organization. A self GET can return no assignment and revision zero without creating a row. An administrator creates an assignment explicitly using the authorized opaque profile picker, then uses revisions for later position/unit changes. Keep personal preferences and tenant directory data separate.

Corporate identity providers, group discovery/mappings, personal-token administration and MCP OAuth client registration require the appropriate ordinary verified identity. A PAT with a management-looking scope cannot bypass an identity-only gate. Read capability/readiness responses before selecting provider operations; do not assume every IdP exposes the same directory or photo data. Keep credentials server-side and handle returned one-time client/token secrets privately and once.

For application registrations, distinguish registering a client from the current user's consent and from an application successfully connecting. Authorized-application revocation affects the current user's grant; rotating an OAuth client secret is a separate administrator action. See [application registration](register-applications.md), [API permissions](api-permissions.md) and [people and organization](people-and-organization.md) for their exact boundaries.

## Finish with a response and recovery decision

Inspect the typed response for the new canonical identity, current revision and observed state. Keep safe request-reference metadata for support. On `401`, repair the host's identity flow; on `403`, discard denied private data and recheck current authority. On a revision conflict, display the newer state before asking again. On a timeout or disconnected write, reconcile the original operation and saved state before any further mutation.

Audit reads require `audit:read`; they are a view of authorized recorded activity, not a source of new authority. Keep private payloads, provider credentials and one-time secrets out of logs. Bound downloads to a caller-controlled new path or storage object, treat returned filenames as metadata, and clear cached binaries when the authorized context ends. Async cancellation controls the owned HTTP operation; durable jobs, runs and exports retain their own lifetimes.
