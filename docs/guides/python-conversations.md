<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Python: conversations, streaming and evidence

Use the [Python client setup](headless-python.md) and a current `chat:use` grant for the intended knowledge scope. A conversation is durable server state. The caller supplies the message, selected attachment IDs and a stable request identity; the server chooses only currently authorized resources.

## Submit a scoped run

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

## Require review for later writes

`review_export` then `create_export`, and `review_share` then `create_share`, use the server review's current revision and explicit selections. Downloads read stored immutable outputs; they do not rerun the query. Shares remain authenticated and recheck current source authority. `conversation_evidence` returns the selected evidence manifest.

`proposal`, `confirm_proposal` and `cancel_proposal` keep a catalog suggestion separate from execution. Send `ProposalConfirmation(confirm=True, expected_revision=...)` only after an explicit person reviews the returned diff. Curated intents and external MCP review flows have their own consent/digest rules; an assistant must not obtain or fabricate a component-only approval nonce. See [exports and sharing](exports-sharing.md) and [MCP knowledge management](mcp-knowledge-management.md).
