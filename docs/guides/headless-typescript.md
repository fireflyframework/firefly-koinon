# TypeScript: a client without Angular

Use a verified build of `@fireflyframework/koinon-sdk`, or build it from `sdk/typescript` in the repository. Its development version is not assumed to be published to npm. The client works with Node's standard fetch, Blob and File APIs or with a host-supplied transport; it has no Angular dependency.

The example below targets Node.js 22 or later. Set `KOINON_API_URL` to the API root ending in `/api/v1`, `KOINON_TOKEN` to a scoped personal or API-audience OIDC access token, and `KOINON_TENANT_ID` and `KOINON_WORKSPACE_ID` to authorized identifiers. Replace the environment token callback with your identity provider's renewal function in a long-running service. Tokens are obtained for each request and are never logged.

Save this as `headless.mts`, compile it in your TypeScript project with NodeNext modules, Node types and the DOM library, then run the emitted module. Its entry point only browses documents. Uploading and asking require explicit calls by your application.

```typescript
import {env} from 'node:process';
import {
  FetchTransport, KoinonClient, offsetPages,
  type KnowledgeScope,
} from '@fireflyframework/koinon-sdk';

function required(name: string): string {
  const value = env[name];
  if (!value) throw new Error(`Set ${name} before running this example`);
  return value;
}

export function connect(): KoinonClient {
  return new KoinonClient({transport: new FetchTransport({
    baseUrl: required('KOINON_API_URL'),
    accessToken: () => required('KOINON_TOKEN'),
    credentials: 'omit',
  })});
}

export async function browse(client: KoinonClient, tenant: string, workspace: string) {
  for await (const page of offsetPages(page => client.catalog.list(tenant, {
    workspace_id: workspace, kind: 'document', page, page_size: 25, sort: 'name', order: 'asc',
  }))) {
    for (const document of page.items) console.log(document.id, document.name);
  }
}

export async function* uploadFiles(
  client: KoinonClient, tenant: string, workspace: string, project: string,
  collection: string, files: File[], mode: 'document' | 'dataset' = 'document',
) {
  if (files.length < 1 || files.length > 16) throw new Error('Choose from 1 to 16 files');
  if (files.some(file => file.size > 32 * 1024 * 1024)) throw new Error('Each file must be at most 32 MiB');
  for (const file of files) {
    const receipt = await client.sources.uploadFile(tenant, {
      file, filename: file.name, workspace_id: workspace, project_id: project,
      parent_id: collection, mode,
    });
    yield {filename: file.name, receipt};
  }
}

export async function ask(
  client: KoinonClient, tenant: string, scope: KnowledgeScope, question: string,
  signal?: AbortSignal,
) {
  const settings = await client.organizationChat.get(tenant, {
    ...(scope.workspace_id ? {workspace_id: scope.workspace_id} : {}),
    ...(scope.project_id ? {project_id: scope.project_id} : {}),
  });
  if (!settings.can_run || !settings.default_agent_id) {
    throw new Error("An operator must configure the organization's chat agent");
  }
  const thread = await client.chat.create(tenant, {title: 'Knowledge question', scope});
  const run = await client.chat.submit(tenant, thread.id, {
    agent_id: settings.default_agent_id, message: question, scope,
    client_request_id: crypto.randomUUID(), attachment_ids: [],
  });
  let completed = false;
  for await (const event of client.chat.events(tenant, run.run_id, {signal})) {
    console.log(event.id, event.type);
    if (event.type === 'failed' || event.type === 'cancelled') {
      throw new Error(`Run ended: ${event.type}`);
    }
    if (event.type === 'completed') {
      completed = true;
      break;
    }
  }
  if (!completed) throw new Error('The stream ended without a completed event');
  return {thread, run, audit: await client.chat.audit(tenant, run.run_id)};
}

async function main() {
  const client = connect();
  await client.context();
  await browse(client, required('KOINON_TENANT_ID'), required('KOINON_WORKSPACE_ID'));
}

await main();
```

The fetch transport does not create a background session or require a client close method. A `for await` loop owns its stream; breaking, throwing or aborting releases that response. Aborting it does not cancel the durable run. Call `client.chat.cancel(tenant, run.run_id)` when the user requests cancellation. Pass `lastEventId` only for intentional resumption from the last fully processed event. Your renderer must replace partial message state on `message_reset`.

`uploadFiles` receives immutable `File` objects and yields each accepted receipt before sending the next file. Persist those receipts. The batch stops on failure and makes no promise of atomicity, durable recovery or automatic retries. Use `dataset` for supported workbook/structured formats and `document` for document intake. The server remains responsible for its format, size, extraction and authority checks.

Inspect saved answer messages with `client.chat.messages(tenant, thread.id)` and exact tool data with `client.chat.result(tenant, run.run_id, resultId)`. Only use result IDs recorded for that run. Render OpenUI through registered components, never by executing model-supplied HTML or scripts.

See [typed audit semantics](agents.md#read-the-audit-without-the-frontend), [reviewed export and sharing](exports-sharing.md) and the [generated API reference](../reference/sdk-api.md). Null historical provenance or identity stays unknown even when the current organization configuration is available.
