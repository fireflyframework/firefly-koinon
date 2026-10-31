<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Python: conversations, streaming and evidence

Use the [Python client setup](headless-python.md) and a current `chat:use` grant for the intended knowledge scope. A conversation is durable server state. The caller supplies the message, selected attachment IDs and a stable request identity; the server chooses only currently authorized resources.

## Build the conversation in deliberate stages

Use an already authorized workspace and current `chat:use` authority. This chapter separates saved conversation state, a submitted run, its live event connection, and later reviewed changes. Each has its own identity and lifetime. A token that can read a catalog does not automatically admit a chat run or another person's conversation.

[Download the complete conversation source](../examples/python/README.md). Its default entry point lists the first page of the current owner's saved threads; it does not create a thread, invoke a model, or approve a change. The submit and review helpers are explicitly called functions. Before using them in a host, provide durable storage for the selected thread, request identity, run ID, and event checkpoint.

1. Select or create a saved thread and retain its ID.
2. Inspect the scoped organization chat default and its availability.
3. Retain a stable request ID and exact intended message before submission.
4. Save the returned run ID, then observe events.
5. Reconcile saved messages and audit after the run reaches an observed outcome.
6. Handle any export, share, proposal or curated write as a separate reviewed action.

## Run the read-only chapter

Download `support.py` and the selected chapter file into the same directory, then use the Python environment from setup. [Complete source and build instructions](../examples/python/README.md) include [the entry-point file](../examples/python/conversations.py). Use the organization already selected in `KOINON_TENANT_ID`. Keep credentials in the approved environment rather than adding them to these commands.

```sh
python conversations.py
```

The result prints saved thread IDs, titles and revisions for the current owner. An empty page is valid. Choose one returned thread before adapting the run or review helpers. If authorization fails, return to the setup chapter and inspect current context/scopes instead of broadening the request. The remaining helpers define the intended mutations, but this command does not invoke them.

## Submit a scoped run

First read the saved thread if one already represents this interaction. A new question does not require a new thread. Build the scope from selected authorized IDs, then inspect the saved default. A missing default or `can_run=false` needs an operator decision; do not guess another agent ID or grant access from a model suggestion.

The run input contains the exact message, scope, selected ready attachments, agent, and client request identity. The response is a saved run, not the finished answer. Store its canonical ID before opening the event stream. Thread creation and run submission are separate writes: if either response is lost, reconcile it independently before deciding whether to create more state.


Read the saved organization default instead of inventing an agent ID. `can_run` permits a request; it is not proof that a particular provider, model or tool has completed successfully. An authorized explicit integration can supply another configured agent.

```python
from koinon_sdk import KoinonClient, KnowledgeScope, RunInput, ChatRun, ChatThread

async def create_conversation(
    client: KoinonClient, tenant: str, scope: KnowledgeScope,
) -> ChatThread:
    return await client.create_thread(tenant, title="Knowledge question", scope=scope)

async def start_question(
    client: KoinonClient, tenant: str, thread_id: str, scope: KnowledgeScope,
    question: str, stable_request_id: str,
) -> ChatRun:
    settings = await client.organization_chat_settings(
        tenant, workspace_id=scope.workspace_id, project_id=scope.project_id,
    )
    if not settings.can_run or settings.default_agent_id is None:
        raise RuntimeError("An operator must configure the organization's chat agent")
    return await client.submit_run(tenant, thread_id, RunInput(
        agent_id=settings.default_agent_id, message=question, scope=scope,
        client_request_id=stable_request_id, attachment_ids=[],
    ))
```

Create or retrieve a conversation first and persist its ID. Generate and persist a request ID (for example `str(uuid4())`) and the exact payload before calling `start_question`, then retain the returned run ID. Use that same request identity to reconcile an ambiguous submission; do not silently create another thread/run. If conversation creation itself times out, reconcile `threads` before creating another. `threads`, `thread`, `messages`, folders and revisioned thread patches provide saved history. Message paging uses `before`/`limit`, not artificial page numbers. A saved message's presentation metadata belongs to that message.

Inspect `attachment_capabilities` and the thread's attachment helpers before uploading private files. Only selected, ready attachment IDs belong in `RunInput.attachment_ids`; upload does not automatically promote a file into shared knowledge. Promotion is its own reviewed, revisioned action. See [private attachments](agents.md#private-files-in-chat).

## Organize threads without changing knowledge access

Read the folder list lazily, create a folder only when requested, and retain its current revision for later edits. To move an existing thread, read its current `revision`, show the selected destination, and patch `folder_id` with that reviewed revision. Explicit null removes the folder assignment. Archiving affects saved conversation organization; it does not delete source knowledge or grant another person access. A revision conflict requires a fresh view and decision.

Message history uses its returned cursor (`before`) and limit. Do not send page numbers to a message endpoint or combine unrelated cursors. Keep a thread's saved presentation metadata with its messages. When the authenticated account, tenant, selected thread or permissions change, discard private cached content and ignore late responses from the previous context.

## Own the stream and cancellation separately

```python
from collections.abc import Awaitable, Callable
from koinon_sdk import KoinonClient, StreamEvent

async def consume_run(
    client: KoinonClient, tenant: str, run_id: str,
    checkpoint: Callable[[StreamEvent, str], Awaitable[None]],
    last_processed_id: str | None = None,
    initial_text: str = "",
) -> tuple[str, str, str]:
    partial = initial_text
    async with client.events(tenant, run_id, last_event_id=last_processed_id) as events:
        async for event in events:
            if event.type == "message_reset":
                partial = ""
            elif event.type == "message_delta":
                partial += event.data.text or ""
            await checkpoint(event, partial)
            last_processed_id = event.id
            if event.type in {"completed", "failed", "cancelled"}:
                return last_processed_id, event.type, partial
    raise RuntimeError("Stream ended without a terminal event; reconcile the saved run")
```

The context manager closes the HTTP response on return, failure or task cancellation. For manual iteration, call `await events.aclose()` in `finally`. Closing HTTP does not cancel the durable run: call `cancel_run(tenant, run_id)` only when the user requests cancellation. An explicit retry uses `retry_run`; handle the new run/message cursor and `message_reset` instead of concatenating incompatible partial answers.

Supply a host-owned `checkpoint` callback that durably accepts the event, resulting presentation state and cursor together before returning. On resumption, hydrate `initial_text` and `last_processed_id` from that same checkpoint; handle any structured events your application displays before advancing their cursor. The example returns terminal status explicitly so the caller can distinguish completed, failed and cancelled runs.

Resume intentionally using the last fully processed event ID. The SDK obtains a fresh caller token on a new request, validates SSE framing/content type and never reconnects automatically. If no terminal event arrived, inspect the saved run/thread state rather than calling a model result complete. A failed terminal event also does not constitute a successful answer.

## Keep a recoverable event checkpoint

Treat the reducer's state and last processed event ID as one durable checkpoint. On `message_delta`, update the displayed text; on `message_reset`, replace the prior partial state. Process structured citations, policy and tool-activity events before advancing their cursor. Do not checkpoint merely because bytes arrived over HTTP.

On a reconnect, reload that exact state and cursor, request a new stream, and tolerate a replay after a local crash. The SDK bounds a frame to 1 MiB and releases the response when iteration ends. It does not reconnect or choose which events your application has processed. If the stream ends without a terminal event, read the saved run/messages rather than labeling the partial output a completed answer.

A cancel button has two possible meanings. “Stop watching” closes the local stream or aborts HTTP. “Cancel run” calls the explicit server cancellation operation for the retained run ID. Communicate which action the user chose. A cancellation request can race completion, so inspect the returned/saved state before displaying a terminal outcome.

## Read the recorded evidence

`run_audit(tenant, run_id)` returns the owner-authorized typed `AnswerAudit`. `run_activities` pages public tool activity; `result` reads only a result ID actually recorded for that run. Activity exposes safe summaries and timestamps, not hidden reasoning or raw tool arguments. Render supported OpenUI through registered components; never execute model-supplied HTML or scripts.

| Recorded field | Interpretation |
| --- | --- |
| `generations` | Actual generation identities and start/end observations; missing end time stays incomplete. |
| `sources` and `private_files` | Immutable revisions/hashes used then; current availability and authority are checked separately. |
| `native_reads` | Recorded bounded evidence reads, including explicit truncation and coverage. |
| `sql_attempts` | Submitted SQL, outcome and referenced snapshots; imported DuckDB context is not a live query of the original database. |
| `rlm_tools` | Actual recorded RLM actions; null means unrecorded, not an empty complete trace. |
| `source_provenance_complete` | Independent completeness signal; null is unknown even when receipts exist. |

Keep nullable identities and historical gaps intact. See [knowledge runtime](../concepts/knowledge-runtime.md) and [answer auditing](agents.md#read-the-audit-without-the-frontend).

## Review the exact selected messages

Choose explicit message IDs from the saved conversation before requesting an export or share review. For an export, also choose its supported format and whether to include evidence. Display the returned review's selection, availability and revision; then ask for confirmation in a separate host action. Send only that review ID and expected revision to creation. Do not quietly expand the selection to the whole thread.

For a share, show the current recipient policy and expiration before creating it. The supported authenticated organization policy does not create a public anonymous link, and a recipient still needs current source authority. Review and create use `exports:read/write` or `shares:read/write` plus their dependency scopes and owner/resource checks. After creation, inspect saved export/share state; a download reads stored output rather than rerunning the original query.

A proposal or curated preview is a different review object. Keep its actual diff, target, revision and consent/digest protocol; never substitute an export review, an external receipt, or a model's text for that authority. Ordinary API helpers cannot manufacture a component-only approval nonce. If the server rejects a revision or permission, stop and present the changed state instead of automatically confirming again.

## Require review for later writes

`review_export` then `create_export`, and `review_share` then `create_share`, use the server review's current revision and explicit selections. Downloads read stored immutable outputs; they do not rerun the query. Shares remain authenticated and recheck current source authority. `conversation_evidence` returns the selected evidence manifest.

`proposal`, `confirm_proposal` and `cancel_proposal` keep a catalog suggestion separate from execution. Send `ProposalConfirmation(confirm=True, expected_revision=...)` only after an explicit person reviews the returned diff. Curated intents and external MCP review flows have their own consent/digest rules; an assistant must not obtain or fabricate a component-only approval nonce. See [exports and sharing](exports-sharing.md) and [MCP knowledge management](mcp-knowledge-management.md).
