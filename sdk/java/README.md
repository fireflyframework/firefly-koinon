# firefly koinon Java SDK

A typed, headless client for the koinon knowledge API. Use it from a Java application or service without running the management interface. It requires Java 21 or later and Jackson; it has no dependency on a web framework or the koinon backend package.

This is a development package. Building it locally does not publish an artifact to Maven Central. The [shared operation manifest](../contract/operations.json) records the canonical API boundary and corresponding methods in each language. Retained endpoints outside that contract are not included implicitly.

`client.datasets(tenant).appendFile(dataset, new DatasetFileUpload(path, mediaType), "stable-request")` appends one file and its parsed tables to the existing dataset and returns `DatasetFileAppendResult`. The file-version and table identifiers are canonical. Pending or failed intake blocks query/schema until reconciliation, preserving previous files and snapshots. Native section commits are independent; this is not atomic bulk intake or a recovery helper. Never replay an unknown write outcome automatically. An identical request with the same key returns its retained receipt after current authorization, without repeating native work; a changed payload conflicts. PostgreSQL concurrency and configured-provider acceptance are separate qualification gates.

## Build

From this directory:

```sh
mvn verify
```

Install a qualified local build with `mvn install`, then use these coordinates:

```xml
<dependency>
  <groupId>org.fireflyframework</groupId>
  <artifactId>koinon-sdk</artifactId>
  <version>26.10.0-alpha.1</version>
</dependency>
```

## Connect

```java
import java.net.URI;
import org.fireflyframework.koinon.sdk.KoinonClient;

try (var knowledge = KoinonClient.builder(
        URI.create("https://knowledge.example.org/api/v1"))
    .bearerToken(identity::getAccessToken)
    .build()) {
  var context = knowledge.platform().context();
  var documents = knowledge.documents(organizationId);
}
```

The caller supplies token renewal. The supplier runs for each HTTP request, including when a stream is subscribed to. Use a scoped personal token or an OIDC access token issued for the API audience. Authorization still depends on current membership, role, token scopes and resource boundaries. The SDK cannot grant access.

The client closes its own connections and outstanding requests. If you inject an `HttpClient`, keep redirects disabled and close that client yourself after closing the SDK. Redirects are rejected to keep bearer credentials on the configured API origin.

## API groups

| Accessor | Operations |
| --- | --- |
| `platform()` | Authorized context and capabilities |
| `profile()` | Your profile, preferences and avatar |
| `tokens()` | Scope descriptors, token creation, listing and revocation |
| `catalog(tenant)` | Browse, create, update, archive, restore and delete catalog entries |
| `sources(tenant)` | Upload knowledge sources |
| `documents(tenant)` | Chunks, originals, content updates and reingestion |
| `datasets(tenant)` | Dataset schema, table content/reingestion, exact snapshot provenance and paged history |
| `knowledge(tenant)` | Document search, structured queries and lineage |
| `knowledgeConnections(tenant)` | Role descriptors and model assignments |
| `providers(tenant)` | Model connections and validation |
| `agents(tenant)` | Agent configuration and validation |
| `chatFolders(tenant)` | Scoped folder hierarchy and revisioned history metadata |
| `chatAttachments(tenant)` | Private upload, extraction, selection, originals and explicit promotion |
| `chatProposals(tenant)` | Read a server diff, explicitly confirm or cancel |
| `knowledgeIndexes(tenant)` | Native index plan, durable rebuild, activation, cancellation and resume |
| `identity(tenant)` | Guided corporate identity configuration and verification |
| `exports(tenant)` | Bounded review, immutable authenticated download and cancellation |
| `shares(tenant)` | Reviewed conversation sharing and revocation under current ACL |
| `evidence(tenant)` | Selected conversation source manifests |
| `chat(tenant)` | Conversations, messages, durable runs, events and evidence results |
| `jobs(tenant)` | Authorized processing jobs, status and cancellation |
| `members(tenant)` | Membership and role management |
| `people(tenant)` | Authorized directory and avatar downloads |
| `audit(tenant)` | Organization audit records |
| `configuration(tenant)` | Model, knowledge and deployment observations |

Resource methods have synchronous and asynchronous forms. Asynchronous methods return `CompletableFuture<T>` with the same response DTO. Canceling a future releases its underlying request. Writes are never retried automatically.

## Fields and revisions

Request records expose typed `with…` methods. Patch records distinguish an omitted field from explicit JSON null using `JsonField<T>`. For example, `ProviderInput.empty().clearSecret()` sends `"secret": null`; omitting the field preserves the saved credential. The server determines which fields may be cleared.

`RequestOptions` is immutable. Use `ifMatch` for content revisions and `lastEventId` for explicit stream resumption. Content replacement and reingestion require the current revision. A stale revision is an error; the SDK has no forced-overwrite helper.

## Exact values

Business cells remain typed JSON values. Exact decimals and integers beyond JavaScript's safe range travel as strings, so another language cannot silently round them. Convert only fields whose meaning you know:

```java
import java.math.BigDecimal;
import java.math.BigInteger;
import org.fireflyframework.koinon.sdk.ExactValues;

var amount = ExactValues.decimal(new BigDecimal("12345678901234567890.00100"));
var externalNumber = ExactValues.integer(new BigInteger("9007199254740993"));
```

These helpers preserve decimal scale and return a string for an unsafe integer. They do not convert identifier strings, dates or unknown text automatically. Metadata timestamps use `Instant`; date-only business values remain separate. Raw JSON data is copied defensively.

## Pagination and files

`Page<T>` retains totals, page numbers, sizes, cursors and actor metadata when the server supplies them. `Pages.numbered` and `Pages.cursor` lazily call a typed page loader. They do not prefetch, split local arrays or assume an items-only endpoint supports pagination. Repeated cursors and inconsistent page numbers fail explicitly.

Uploads stream files through multipart requests. `BinaryResponse` includes content type, filename, ETag and the not-modified state. In-memory downloads are bounded to 64 MiB. For larger originals, use `documents(tenant).downloadOriginal(documentId, target, maxBytes, options)` with an explicit byte limit. It removes incomplete temporary files after failure and never replaces an existing destination. A conditional 304 response leaves the destination untouched.

## Streaming and errors

An `EventStream<StreamEvent>` implements `Flow.Publisher` and `AutoCloseable`. It supports one subscriber and honors demand from `Flow.Subscription.request`. Cancel the subscription or close the stream when leaving the view. Closing releases the connection; cancel the durable run through the chat API when you also want processing to stop.

Store the last fully processed event ID. A new stream can pass it with `RequestOptions.lastEventId`; reconnection is explicit. Handle message resets and terminal events, and retrieve evidence through the result endpoint. OpenUI artifacts are data for a registered renderer; the SDK never executes model-produced components, HTML or JavaScript.

`ApiException` exposes HTTP status, the native error code and the support request reference. Network, timeout and decoding failures retain their causes. Interrupted synchronous calls cancel the pending request and restore the interrupted flag. Requests default to a 30-second timeout, configurable through `RequestOptions`. An active event stream stays open until its source finishes or the caller closes it.

## Verification

`mvn verify` compiles Java 21 bytecode with all compiler warnings enabled and warnings treated as errors. Tests check DTO serialization, API coverage, HTTP behavior and streaming. The repository's `tools/sdk/check_java_consumer.py` separately checks the JAR's notices and compiles an external consumer against its runtime dependencies. CI defines Java 21 and 25 jobs. A workflow definition is not evidence that a hosted run has passed.

Package validation, live authenticated API checks, model acceptance and production qualification are separate checks. SDK coverage does not establish that a provider or deployment is ready.

Copyright 2026 Firefly Software Foundation Made with <3. Licensed under [Apache-2.0](../../LICENSE); see [NOTICE](../../NOTICE).


The current source contract includes revisioned chat folders/history, native index lifecycle, corporate identity, and ten private attachment routes. Inspect thread attachment capabilities before upload. Only explicitly selected attachment IDs enter a run; files remain owner/tenant/conversation scoped. Upload/retry and index create/resume use caller-supplied idempotency keys. Native tool activity carries a stable call ID, safe summary, server timestamps and an optional authorized evidence reference, without tool arguments or hidden reasoning.

Known corporate settings/credential variants are typed. Omitted fields and explicit-null credential removal stay distinct; credential-bearing objects redact diagnostic representations. This evolving source contract is distinct from earlier frozen alpha artifacts. Private promotion uses an explicit revisioned action and stable idempotency key. Exports and shares require an explicit bounded review followed by creation with the returned revision. Export downloads use stored immutable results; they never rerun a query. Shares remain authenticated and recheck current source authority.

## Qualified glossary operations

`structuredGlossary(tenant, workspace)` and `structuredAgentGlossary(tenant, workspace)` expose typed list/get/create/update/remove plus asynchronous variants. The server requires the structured module and its native resource admission. `GlossaryTermRead.updatedAt()` remains an unparsed string so `update` and `remove` can send its exact microsecond timestamp as `If-Match`; do not convert it through a date formatter. A `GlossaryPage` can have an unknown total and retains native limit/offset/hasMore metadata. These operations are listed separately from the canonical operation count.

Export/share creation requires a reviewed snapshot and matching revision. Downloads read immutable stored bytes without rerunning SQL. Proposal confirmation uses `ProposalConfirmation` with an explicit true value after a person reviews the server diff; no evidence renderer or stream consumer applies changes automatically.


`chat(tenant).audit(runId)` returns the owner-authorized `AnswerAudit`. Receipt presence and `source_provenance_complete` are separate; null completeness means historical data was not recorded. Used source revisions and private-file SHA/revisions remain immutable, while current availability is checked separately. SQL attempts retain the actual submitted statement, execution outcome and referenced table snapshots. Recorded DuckDB database/catalog context identifies imported-snapshot execution, not a live query against an original remote database. Original connection/file lineage remains null when it was not observed. A generation with no recorded end time must not be presented as completed. Proposal-only responses use `review_required` and require a separate explicit confirmation.

`client.organizationChat(tenant).get(OrganizationChatFilter.empty().withWorkspaceId(workspace))` reads the saved organization default. Update with `OrganizationChatSettingsInput.empty().withDefaultAgentId(agentId).withExpectedRevision(current.revision())`; use `clearDefaultAgentId()` for explicit null. The server requires organization-level `agents:write` and rejects stale revisions. Explicit run submissions continue supplying `agent_id`; the default does not grant knowledge access.
