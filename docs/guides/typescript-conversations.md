<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# TypeScript: conversations, streaming and evidence

Use the [TypeScript setup](headless-typescript.md) and current `chat:use` authority in the intended scope. Conversations and runs are durable server state; an HTTP stream is one view of that state.

## Start a scoped question

Read the organization default and submit its actual agent ID when `can_run` is true. This permits an explicit request; it does not certify a provider/model/tool execution. An authorized integration can choose another configured agent explicitly.

```typescript
import {KoinonClient, type KnowledgeScope} from '@fireflyframework/koinon-sdk';

export async function createConversation(
  client: KoinonClient, tenant: string, scope: KnowledgeScope,
) {
  return client.chat.create(tenant, {title: 'Knowledge question', scope});
}

export async function startQuestion(
  client: KoinonClient, tenant: string, threadId: string, scope: KnowledgeScope,
  question: string, stableRequestId: string,
) {
  const settings = await client.organizationChat.get(tenant, {
    ...(scope.workspace_id ? {workspace_id: scope.workspace_id} : {}),
    ...(scope.project_id ? {project_id: scope.project_id} : {}),
  });
  if (!settings.can_run || !settings.default_agent_id) {
    throw new Error("An operator must configure the organization's chat agent");
  }
  return client.chat.submit(tenant, threadId, {
    agent_id: settings.default_agent_id, message: question, scope,
    client_request_id: stableRequestId, attachment_ids: [],
  });
}
```

Create or retrieve a conversation first and persist its ID. Generate and retain a request ID (for example `crypto.randomUUID()`) and exact payload before calling `startQuestion`, then save the returned run ID. Reconcile an ambiguous submission with that identity instead of creating another run. If thread creation itself times out, reconcile saved threads first. Saved threads, messages and revisioned folders are exposed through `chat`. Message history uses `before`/`limit`; preserve saved presentation metadata and event cursors.

Read `chat.attachments.capabilities` and the thread attachment state before uploading. Only explicitly selected ready IDs enter `attachment_ids`. Private upload is not shared knowledge ingestion; promotion requires a distinct reviewed action and current revision. See [private files in chat](agents.md#private-files-in-chat).

## Consume and resume events deliberately

```typescript
import {KoinonClient, type StreamEvent, type ChatEventData} from '@fireflyframework/koinon-sdk';

export async function consumeRun(
  client: KoinonClient, tenant: string, runId: string,
  checkpoint: (event: StreamEvent<ChatEventData>, text: string) => Promise<void>,
  signal?: AbortSignal, lastProcessedId?: string,
  initialText = '',
): Promise<{lastProcessedId: string; terminal: string; text: string}> {
  let text = initialText;
  for await (const event of client.chat.events(tenant, runId, {
    signal, ...(lastProcessedId !== undefined ? {lastEventId: lastProcessedId} : {}),
  })) {
    if (event.type === 'message_reset') {
      text = '';
    } else if (event.type === 'message_delta') {
      text += event.data.text ?? '';
    }
    await checkpoint(event, text);
    lastProcessedId = event.id;
    if (['completed', 'failed', 'cancelled'].includes(event.type)) {
      return {lastProcessedId, terminal: event.type, text};
    }
  }
  throw new Error('Stream ended without a terminal event; reconcile the saved run');
}
```

Breaking, returning, throwing or aborting closes that response. It does not cancel the durable run: use `chat.cancel(tenant, runId)` only when the user requests cancellation. An explicit `chat.retry` follows server retry behavior; apply its run/message cursor and `message_reset` rather than appending incompatible partial answers.

Provide a host-owned `checkpoint` callback that durably accepts the event, resulting presentation state and cursor together before resolving. Resume with `initialText` and `lastProcessedId` from the same checkpoint; handle any structured events your application displays before advancing their cursor. The returned terminal status keeps failed/cancelled outcomes separate from completed answers.

Supply `lastEventId` only for intentional resumption from the last fully processed event. SSE content type, fragmented UTF-8 and frame bounds are validated. The SDK never reconnects automatically. A fresh stream request obtains a fresh bearer callback result. Missing terminal events require saved-state reconciliation; `failed` is terminal but is not a successful answer.

## Read the recorded audit

`chat.audit` returns typed owner-authorized `AnswerAudit`; `chat.activities` pages public tool summaries, and `chat.result` reads a result ID actually returned for that run. Use registered OpenUI components for supported results, never model-supplied executable HTML or scripts.

| Field | Preserve this meaning |
| --- | --- |
| `generations` | Recorded execution identities and start/end observations; a missing end time stays incomplete. |
| `sources`, `private_files` | Exact historical revisions/hashes used then; current availability/authority remains separate. |
| `native_reads` | Recorded bounded reads with actual coverage/truncation. |
| `sql_attempts` | Submitted SQL, outcome and snapshots; imported DuckDB context is not a live query of the original database. |
| `rlm_tools` | Recorded RLM actions; null means unrecorded, and a list alone does not prove completeness. |
| `source_provenance_complete` | Independent completeness flag; null means unknown. |

Do not infer a historical source/model identity from current configuration. See [knowledge runtime](../concepts/knowledge-runtime.md) and [audit semantics](agents.md#read-the-audit-without-the-frontend).

## Review later exports, shares and proposals

`exports.review/create` and `shares.review/create` require explicit bounded selections and the current review revision. `exports.download` reads a stored immutable output rather than rerunning SQL. Shares remain authenticated and recheck source authority. `evidence.conversation` returns the selected source/message manifest.

`chat.proposals.get/confirm/cancel` separates a suggestion from execution. Send `{confirm: true, expected_revision}` only after a person reviews the server diff. Curated and external review flows have separate digest/consent rules; a client must not fabricate or obtain a component-only approval nonce. See [exports and sharing](exports-sharing.md) and [MCP knowledge management](mcp-knowledge-management.md).
