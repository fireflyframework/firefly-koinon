# koinon Python SDK

Typed async API client for backend integrations. The consumer supplies a short-lived bearer token callback and owns renewal. The SDK re-reads that callback for every request and never stores a client secret or refresh token. All tenant/resource authorization remains on the server.

```python
from koinon_sdk import KoinonClient

async with KoinonClient("https://knowledge.example.org/api/v1", token_provider=my_token) as knowledge:
    context = await knowledge.context()
    entries = await knowledge.catalog("north", kind="document")
```

Use the bearer API prefix, not the browser BFF. Native pyfly applications can provide the client through a configuration bean and inject it into services. Close the client during application shutdown. HTTP errors retain server problem details; writes are not automatically retried. Build and test the installed wheel before consumer rollout.

Assistant setup and streaming use the same standalone client:

```python
from koinon_sdk import KnowledgeScope, RunInput

async with KoinonClient("https://knowledge.example.org/api/v1", token_provider=my_token) as knowledge:
    agents = await knowledge.agents("north")
    thread = await knowledge.create_thread("north", scope=KnowledgeScope(workspace_id="workspace-id"))
    run = await knowledge.submit_run(
        "north",
        thread.id,
        RunInput(
            agent_id=agents.items[0].id,
            message="Summarize this workspace",
            client_request_id="caller-generated-stable-request-id",
        ),
    )
    async with knowledge.events("north", run.run_id, last_event_id="0") as events:
        async for event in events:
            print(event.id, event.type, event.data.text)
```

Check agent readiness and choose an authorized agent before submission. Provider methods are `configuration`, `create_provider`, `update_provider`, and `validate_provider`; provider inputs hide secrets in their representation and provider responses never include them. Agent methods are `agents`, `create_agent`, `update_agent`, and `validate_agent`. Chat methods also include `threads`, `messages`, `cancel_run`, `retry_run`, and `result` for authorized evidence.

Keep the last fully processed event ID and pass it as `last_event_id` to resume. Event types include `message_reset`; clear the prior rendered message when that event starts an explicit retried run. The SDK does not reconnect streams or retry writes automatically. Reusing the caller's `client_request_id` with the same payload lets the server identify an existing submission. Explicit `retry_run` starts the server's reviewed retry behavior; closing a stream does not cancel the server job. Use `cancel_run` for cancellation.

Use `async with` around event streams, or call `await events.aclose()` in a `finally` block when leaving iteration early. Cancelling the consuming task closes its HTTP response. Streams validate content type, decode fragmented UTF-8/multiline JSON events, and reject frames larger than 1 MiB. Request a new stream to obtain a fresh caller token; token renewal remains the consumer's responsibility.

This package depends only on HTTPX and Pydantic at runtime. It does not import the backend, Angular, or pyfly. Configure model credentials on the server through an authorized provider workflow; never place them in chat input or client logs.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.

Profiles use `profile()`, `update_profile(ProfileUpdate(...))`, `set_avatar(bytes, media_type="image/png")`, `avatar()` and `delete_avatar()`. Avatar uploads are raw bytes; the backend returns sanitized JPEG thumbnails. `people(tenant_id, workspace_id=...)` is an authorized administration directory. Profile names do not confer permissions or replace canonical subjects.

The client preserves raw dates and numeric values. Locale/timezone/response-language preferences are separate presentation metadata; chat messages retain their `presentation` metadata. After an explicit retry or conversation hydration, use the returned run/message `event_cursor` as the stream resume boundary. Catalog `archive()` and `restore()` are explicit reversible POST operations returning the entry; `catalog(..., include_archived=True)` requests the archive view. Entry status belongs to ingestion/indexing and cannot be changed through `update()`.

Use an interactive identity to call `token_scopes(tenant_id, workspace_id=...)`, `create_token(TokenInput(...))`, `tokens()` and `revoke_token(id)`. Choose an aware expiry and the least required scopes/resources. Token creation returns its secret once as `SecretStr`; access `created.token.get_secret_value()` only to place it in your secret manager. List responses contain metadata only. Personal tokens cannot create additional tokens, and their effective access remains bounded by current server-side grants. A normal SDK `token_provider` can supply a personal token just as it supplies an OIDC access token.

Document readers use `document_chunks(tenant_id, document_id, offset=0, limit=50, page=None, section=None, q=None)` and `document_original(tenant_id, document_id)`. Chunk section paths are nullable strings. Original downloads return authenticated bytes and do not write local files or follow redirects. Each call obtains a fresh caller token. `ApiError.transaction_id` (also available as `request_id`) preserves native problem-details `transactionId` or legacy error references for operator correlation.

The canonical operation index and standalone wire schemas are in `sdk/contract/operations.json` and `schemas.json` at the repository root. The current development contract has 137 canonical versioned operations with named helpers. Qualified retained glossary operations are listed separately from that count. Public operator probes and browser-only `/auth/me` are outside the headless versioned API.

`append_dataset_file(tenant, dataset, filename="more.csv", content=file_bytes, idempotency_key="stable-request")` appends one file and its parsed tables to an existing dataset and returns `DatasetFileAppendResult`. It preserves previous snapshots and returns canonical file-version/table identities. Pending or failed intake blocks dataset query/schema until reconciliation; writes are never automatically replayed. Native section commits are independent, so this is not an atomic bulk upload or a recovery API. An identical request with the same key returns its retained receipt after current authorization, without repeating native work; a changed payload conflicts. PostgreSQL concurrency and configured-provider acceptance are separate qualification gates.

`table_provenance(tenant, dataset, table, snapshot_id=used_snapshot)` reads the exact selected snapshot. `table_snapshots(..., page=1, page_size=25)` returns server-paged history and its separate current snapshot. `status="not_recorded"` preserves unknown historical origins; it does not substitute current file metadata. Recorded `level="file_section"` does not claim row or cell lineage.

Use `add_member(MemberInput(...))`, `update_member(MemberUpdate(...))`, and `remove_member` for grants; `members(..., workspace_id=...)` is the declared directory filter. Use `job` and `cancel_job` for a single authorized durable job. Catalog `delete` is distinct from reversible `archive` and may be rejected by lifecycle policy. Agents, threads, catalog, and personal-token lists accept their server paging/filter arguments; membership and audit lists use actual SQL paging; jobs currently return items-only pages.

`knowledge_roles`, `knowledge_connections`, `knowledge_connection`, `create_knowledge_connection`, `update_knowledge_connection`, and `delete_knowledge_connection` expose explicit tenant defaults/workspace assignments. Connection updates/deletion require the current revision. These assignments select model roles; embeddings remain explicit and index compatibility remains server-enforced.

Provider `api` is explicit (`chat`, `responses`, or `messages`) and validated against provider kind. Existing OpenAI configurations retain Chat Completions. Native model options use `ModelParameters`; arbitrary class paths and additional client parameters are rejected. Provider discovery is separate from chat, streaming, and successful tool observations. Use agent `can_run` to offer an explicit unverified trial; unknown prerequisites are never ready. Omit a provider secret to preserve it, and pass `secret=None` explicitly to remove it.

`document_download`, `avatar_download`, and `person_avatar` return `BinaryDownload` with bytes, ETag, content type, filename, and explicit authorized-avatar `not_modified`. The older bytes-only original/avatar helpers remain available. A document replacement/re-ingestion requires its current unquoted `expected_sha256`; a table requires `expected_snapshot_id`. The helpers quote the `If-Match` wire header. Document chunk invalidation acknowledgment defaults to false and is never inferred. Replacement helpers accept a filename and bytes, construct multipart boundaries, and never force an overwrite.

Exact raw cells are JSON strings for decimals and integers outside ±9007199254740991. The client never converts those strings to float. Use `exact_decimal(Decimal("1.2300"))` to emit `"1.2300"` and `exact_integer(9007199254740992)` to emit `"9007199254740992"` in opaque request metadata. Finite Decimal input is required; boolean integer coercion is rejected. Binary floats cannot recover a decimal already rounded by the caller.

`offset_pages(lambda page: client.catalog(tenant, page=page))` and `cursor_pages(lambda after: client.people(tenant, after=after))` lazily yield typed pages. They never prefetch or slice client data. Items-only endpoints are fetched once. Ignored page numbers and repeated cursors fail rather than silently looping. Close a partially consumed async generator; task cancellation propagates to its current HTTP callback.


The current source contract includes revisioned chat folders/history, native index lifecycle, corporate identity, and ten private attachment routes. Inspect thread attachment capabilities before upload. Only explicitly selected attachment IDs enter a run; files remain owner/tenant/conversation scoped. Upload/retry and index create/resume use caller-supplied idempotency keys. Native tool activity carries a stable call ID, safe summary, server timestamps and an optional authorized evidence reference, without tool arguments or hidden reasoning.

Known corporate settings/credential variants are typed. Omitted fields and explicit-null credential removal stay distinct; credential-bearing objects redact diagnostic representations. This evolving source contract is distinct from earlier frozen alpha artifacts. Private promotion uses an explicit revisioned action and stable idempotency key. Exports and shares require an explicit bounded review followed by creation with the returned revision. Export downloads use stored immutable results; they never rerun a query. Shares remain authenticated and recheck current source authority.

`review_export` accepts a discriminated `ConversationExportInput` or `QueryResultExportInput`. Use `create_export`, `exports`, `export`, `export_download` and `cancel_export` for its immutable result. `review_share`, `create_share`, `shares`, `share` and `revoke_share` retain explicit owner/recipient authority. `conversation_evidence` returns the selected message/source manifest; unknown historical provenance remains incomplete.

The proposal helpers are `proposal`, `confirm_proposal` and `cancel_proposal`. Confirmation requires `ProposalConfirmation(confirm=True, expected_revision=...)` after the person reviews the server diff. The SDK never confirms a model-produced proposal automatically.

Structured glossary CRUD uses `glossary_terms`, `glossary_term`, `create_glossary_term`, `update_glossary_term` and `delete_glossary_term`, with canonical tenant/workspace arguments and optional `agent=True`. Pass the exact unparsed `GlossaryTermRead.updated_at` string as `expected_updated_at`; the helper quotes it for `If-Match`. `GlossaryPage` preserves native limit/offset/has_more metadata and an unknown total. These retained operations depend on the structured module's explicit admission and are not counted as canonical routes.


`run_audit(tenant_id, run_id)` returns the owner-authorized `AnswerAudit`. Receipt presence and `source_provenance_complete` are separate; null completeness means historical data was not recorded. Used source revisions and private-file SHA/revisions remain immutable, while current availability is checked separately. SQL attempts retain the actual submitted statement, execution outcome and referenced table snapshots. Recorded DuckDB database/catalog context identifies imported-snapshot execution, not a live query against an original remote database. Original connection/file lineage remains null when it was not observed. A generation with no recorded end time must not be presented as completed. Proposal-only responses use `review_required` and require a separate explicit confirmation.

Coordinate reads pin an exact snapshot and use named parser/dependency/header-cell DTOs. They expose only recorded mappings; unknown or partial coverage stays explicit. Document replacement and reingestion keep the raw `If-Match` digest separate from the paired source-version/extraction preconditions.

Knowledge intents are private previews, not repository writes. Confirmation requires explicit user consent bound to the reviewed revision and digest, plus current write permissions. A typed `pending` response means the commit outcome is unresolved; it must not be shown as confirmed or retried as a new write. Drafts preserve the current published serving version. Curated knowledge sharing/export and deriving a new item from another knowledge version remain explicitly unqualified.
