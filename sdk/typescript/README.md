# koinon TypeScript SDK

A framework-neutral client for the firefly koinon management API. Angular components, custom elements, server applications and other frontends use the same typed contracts. The caller owns authentication and transport. The SDK does not store credentials, control routing or access browser globals.

```ts
import {KoinonClient, FetchTransport} from '@fireflyframework/koinon-sdk';
const client = new KoinonClient({transport: new FetchTransport({
  baseUrl: '/bff/api/v1',
  csrfToken: () => readCsrfCookie(), // supplied by the host
})});
const context = await client.context();
const entries = await client.catalog.list(context.tenants[0].id, {kind: 'document'});
```

Server/API clients use `/api/v1` and an `accessToken` callback returning a short-lived scoped bearer token. Browser sessions use `/bff/api/v1`, credentials included and a fresh decoded `XSRF-TOKEN` value in `X-XSRF-TOKEN` on writes. Cookie and bearer authority are separated by the server. Do not attach bearer tokens to BFF requests. Tenant selection never grants membership.

Hosts can implement `KoinonTransport` instead of using `FetchTransport`. Its `request<T>(method,path,options)` receives API-relative paths and supports bodies, query parameters, headers and AbortSignal. Uploads preserve FormData and its browser-selected multipart boundary. KoinonError retains status, problem code and request identity. Redirects are rejected to keep credentials and request bodies on the configured API origin. Writes are never automatically retried; job submissions require explicit idempotency.

Build/test: `npm ci`, `npm test`. Installed-consumer acceptance and API integration acceptance are separate gates.

The source-backed canonical index and wire DTO schemas live in `sdk/contract/operations.json` and `schemas.json` at the repository root. The current development contract has 137 canonical versioned operations with helpers; retained routes are excluded except the separately listed qualified glossary operations. Operator probes and cookie-only `/auth/me` are outside the headless versioned API.

`dataset.tableProvenance(tenant, dataset, table, usedSnapshot)` reads an exact snapshot. `dataset.tableSnapshots(tenant, dataset, table, {query:{page:1,page_size:25}})` returns server-paged history and a separate current snapshot. A `not_recorded` origin remains unknown; `file_section` coverage is not row or cell lineage.

`dataset.appendFile(tenant, dataset, file, 'stable-request', {filename:'more.csv'})` appends one file and its parsed tables to the existing dataset and returns `DatasetFileAppendResult`. Pending or failed intake blocks query/schema until reconciliation while retaining previous files and snapshots. It is not atomic bulk intake or a recovery helper; never replay an unknown write outcome automatically. An identical request with the same key returns its retained receipt after current authorization, without repeating native work; a changed payload conflicts. PostgreSQL concurrency and configured-provider acceptance remain separate qualification gates.

Use the bearer API directly for headless integrations:

```ts
const client = new KoinonClient({transport: new FetchTransport({
  baseUrl: 'https://knowledge.example.org/api/v1',
  accessToken: myFreshBearer,
  credentials: 'omit',
})});
```

The client includes `people`, `members`, `jobs`, `documents`, `dataset`, `knowledgeConnections`, `providers`, `agents`, `chat`, `profile`, and `tokens`. Catalog/agent/thread/token filters use actual server pagination; members and audit lists use server paging; jobs lists are currently items-only. Knowledge roles are explicit tenant defaults or workspace assignments with revision guards. Model discovery is separate from successful chat, stream, and tool observations. Agent `can_run` permits an explicit unverified trial. Provider `api` selects the supported native API, and `model_options` contains only bounded native options. Secret omission preserves the credential; explicit null removes it.

`documents.download`, `profile.avatarDownload`, and `people.avatar` return `BinaryDownload` metadata plus Blob. The existing Blob helpers remain available. Authorized avatar304 is explicit and no cross-user cache is maintained. Content replacements/re-ingestion require current digest/snapshot `If-Match`; document acknowledgment is explicit and defaults false. Supply a File or `filename` for unnamed Blobs. `sources.uploadFile` builds typed upload fields; the original FormData helper remains available. Multipart boundaries belong to the transport.

`chat.events` returns an async iterable. Keep the last fully processed event ID and provide the `Last-Event-ID` header to reconnect. Break/return from the iterator or abort its signal to close HTTP; use `chat.cancel` to cancel the durable run. Handle `message_reset` by resetting the prior rendered message. No reconnect or write retry occurs automatically. Parsing validates stream MIME, split UTF8/CRLF/BOM, multiline data and a 1MiB UTF8 frame budget; incomplete EOF frames are not emitted.

Raw exact decimal and unsafe-integer cells remain strings. `exactDecimal('1.2300')` validates a plain decimal string while preserving scale; `exactInteger(9007199254740992n)` returns a decimal string and returns a number only within ±9007199254740991. No implicit BigInt/boolean/float coercion is performed. Formatting preferences are separate presentation metadata.

`offsetPages((page, signal) => client.catalog.list(tenant, {page}, {signal}), 1, signal)` and `cursorPages((after, signal) => client.people.list(tenant, {after}, {signal}), signal)` lazily yield typed pages. No prefetch, client slicing, or artificial pages are introduced; items-only endpoints are fetched once. Ignored page numbers/repeated cursors fail. The optional signal is forwarded to each caller-owned fetch and checked before advancing.

Copyright 2026 Firefly Software Foundation. Apache-2.0. Made with <3.


The current source contract includes revisioned chat folders/history, native index lifecycle, corporate identity, and ten private attachment routes. Inspect thread attachment capabilities before upload. Only explicitly selected attachment IDs enter a run; files remain owner/tenant/conversation scoped. Upload/retry and index create/resume use caller-supplied idempotency keys. Native tool activity carries a stable call ID, safe summary, server timestamps and an optional authorized evidence reference, without tool arguments or hidden reasoning.

Known corporate settings/credential variants are typed. Omitted fields and explicit-null credential removal stay distinct; the SDK does not log credentials; callers must treat request objects as secrets. This evolving source contract is distinct from earlier frozen alpha artifacts. Private promotion uses an explicit revisioned action and stable idempotency key. Exports and shares require an explicit bounded review followed by creation with the returned revision. Export downloads use stored immutable results; they never rerun a query. Shares remain authenticated and recheck current source authority.

`exports.review/create/list/get/download/cancel`, `shares.review/create/list/get/revoke` and `evidence.conversation` expose typed bounded review and immutable output contracts. The review input is the discriminated `ExportReviewRequest` union. Preserve unknown completeness/cap metadata instead of claiming a full query result.

`chat.proposals.get/confirm/cancel` requires explicit human review before `{confirm:true, expected_revision}` is sent. Evidence rendering alone never confirms a proposal. `structured.glossary` and `structured.agentGlossary` expose list/get/create/update/remove with canonical tenant/workspace arguments. Update/remove take the exact returned `updated_at` string; never round it through `Date`. Their native offset/limit/has_more page is separate from canonical page-number endpoints.


`chat.audit(tenantId, runId)` returns the owner-authorized `AnswerAudit`. Receipt presence and `source_provenance_complete` are separate; null completeness means historical data was not recorded. Used source revisions and private-file SHA/revisions remain immutable, while current availability is checked separately. SQL attempts retain the actual submitted statement, execution outcome and referenced table snapshots. Recorded DuckDB database/catalog context identifies imported-snapshot execution, not a live query against an original remote database. Original connection/file lineage remains null when it was not observed. A generation with no recorded end time must not be presented as completed. Proposal-only responses use `review_required` and require a separate explicit confirmation.

Coordinate reads pin an exact snapshot and use named parser/dependency/header-cell DTOs. They expose only recorded mappings; unknown or partial coverage stays explicit. Document replacement and reingestion keep the raw `If-Match` digest separate from the paired source-version/extraction preconditions.

Knowledge intents are private previews, not repository writes. Confirmation requires explicit user consent bound to the reviewed revision and digest, plus current write permissions. A typed `pending` response means the commit outcome is unresolved; it must not be shown as confirmed or retried as a new write. Drafts preserve the current published serving version. Curated knowledge sharing/export and deriving a new item from another knowledge version remain explicitly unqualified.

`client.organizationChat.get(tenant, {workspace_id, project_id})` reads the saved organization default. `client.organizationChat.update(tenant, {default_agent_id: agentId, expected_revision: current.revision})` updates it; pass explicit null to clear. The server requires organization-level `agents:write` and rejects stale revisions. Standard chat uses this default only when `can_run` is true; explicit run submissions still supply an actual `agent_id`.
