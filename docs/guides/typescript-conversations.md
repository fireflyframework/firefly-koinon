<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# TypeScript: conversations, streaming and evidence

Use the [TypeScript setup](headless-typescript.md) and current `chat:use` authority in the intended scope. Conversations and runs are durable server state; an HTTP stream is one view of that state.

## Build the conversation in deliberate stages

Use an already authorized workspace and current `chat:use` authority. This chapter separates saved conversation state, a submitted run, its live event connection, and later reviewed changes. Each has its own identity and lifetime. A token that can read a catalog does not automatically admit a chat run or another person's conversation.

[Download the complete conversation source](../examples/typescript/README.md). Its default entry point lists the first page of the current owner's saved threads; it does not create a thread, invoke a model, or approve a change. The submit and review helpers are explicitly called functions. Before using them in a host, provide durable storage for the selected thread, request identity, run ID, and event checkpoint.

1. Select or create a saved thread and retain its ID.
2. Inspect the scoped organization chat default and its availability.
3. Retain a stable request ID and exact intended message before submission.
4. Save the returned run ID, then observe events.
5. Reconcile saved messages and audit after the run reaches an observed outcome.
6. Handle any export, share, proposal or curated write as a separate reviewed action.

## Run the read-only chapter

Download `support.mts`, the selected chapter module and `tsconfig.json` together, then use the Node package from setup. [Complete source and build instructions](../examples/typescript/README.md) include [the entry-point file](../examples/typescript/conversations.mts). Use the organization already selected in `KOINON_TENANT_ID`. Keep credentials in the approved environment rather than adding them to these commands.

```sh
npx tsc -p tsconfig.json
node dist/conversations.mjs
```

The result prints saved thread IDs, titles and revisions for the current owner. An empty page is valid. Choose one returned thread before adapting the run or review helpers. If authorization fails, return to the setup chapter and inspect current context/scopes instead of broadening the request. The remaining helpers define the intended mutations, but this command does not invoke them.

## Start a scoped question

First read the saved thread if one already represents this interaction. A new question does not require a new thread. Build the scope from selected authorized IDs, then inspect the saved default. A missing default or `can_run=false` needs an operator decision; do not guess another agent ID or grant access from a model suggestion.

The run input contains the exact message, scope, selected ready attachments, agent, and client request identity. The response is a saved run, not the finished answer. Store its canonical ID before opening the event stream. Thread creation and run submission are separate writes: if either response is lost, reconcile it independently before deciding whether to create more state.


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

## Organize threads without changing knowledge access

Read the folder list lazily, create a folder only when requested, and retain its current revision for later edits. To move an existing thread, read its current `revision`, show the selected destination, and patch `folder_id` with that reviewed revision. Explicit null removes the folder assignment. Archiving affects saved conversation organization; it does not delete source knowledge or grant another person access. A revision conflict requires a fresh view and decision.

Message history uses its returned cursor (`before`) and limit. Do not send page numbers to a message endpoint or combine unrelated cursors. Keep a thread's saved presentation metadata with its messages. When the authenticated account, tenant, selected thread or permissions change, discard private cached content and ignore late responses from the previous context.

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

## Keep a recoverable event checkpoint

Treat the reducer's state and last processed event ID as one durable checkpoint. On `message_delta`, update the displayed text; on `message_reset`, replace the prior partial state. Process structured citations, policy and tool-activity events before advancing their cursor. Do not checkpoint merely because bytes arrived over HTTP.

On a reconnect, reload that exact state and cursor, request a new stream, and tolerate a replay after a local crash. The SDK bounds a frame to 1 MiB and releases the response when iteration ends. It does not reconnect or choose which events your application has processed. If the stream ends without a terminal event, read the saved run/messages rather than labeling the partial output a completed answer.

A cancel button has two possible meanings. “Stop watching” closes the local stream or aborts HTTP. “Cancel run” calls the explicit server cancellation operation for the retained run ID. Communicate which action the user chose. A cancellation request can race completion, so inspect the returned/saved state before displaying a terminal outcome.

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

## Review the exact selected messages

Choose explicit message IDs from the saved conversation before requesting an export or share review. For an export, also choose its supported format and whether to include evidence. Display the returned review's selection, availability and revision; then ask for confirmation in a separate host action. Send only that review ID and expected revision to creation. Do not quietly expand the selection to the whole thread.

For a share, show the current recipient policy and expiration before creating it. The supported authenticated organization policy does not create a public anonymous link, and a recipient still needs current source authority. Review and create use `exports:read/write` or `shares:read/write` plus their dependency scopes and owner/resource checks. After creation, inspect saved export/share state; a download reads stored output rather than rerunning the original query.

A proposal or curated preview is a different review object. Keep its actual diff, target, revision and consent/digest protocol; never substitute an export review, an external receipt, or a model's text for that authority. Ordinary API helpers cannot manufacture a component-only approval nonce. If the server rejects a revision or permission, stop and present the changed state instead of automatically confirming again.

## Review later exports, shares and proposals

`exports.review/create` and `shares.review/create` require explicit bounded selections and the current review revision. `exports.download` reads a stored immutable output rather than rerunning SQL. Shares remain authenticated and recheck source authority. `evidence.conversation` returns the selected source/message manifest.

`chat.proposals.get/confirm/cancel` separates a suggestion from execution. Send `{confirm: true, expected_revision}` only after a person reviews the server diff. Curated and external review flows have separate digest/consent rules; a client must not fabricate or obtain a component-only approval nonce. See [exports and sharing](exports-sharing.md) and [MCP knowledge management](mcp-knowledge-management.md).
