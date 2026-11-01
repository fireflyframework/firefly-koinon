<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# firefly koinon Java SDK

A typed, headless client for the koinon API. Use it in **Java 21 or later** with the JDK HTTP client and Jackson; no backend package or web framework is required. Resource APIs have synchronous and `CompletableFuture` methods, typed request/response records, bounded binary downloads and demand-driven SSE streams.

## Build and install

From the repository root:

```sh
mvn --batch-mode --no-transfer-progress -f sdk/java/pom.xml verify
mvn --batch-mode --no-transfer-progress -f sdk/java/pom.xml install
```

From this directory, the equivalent commands are `mvn verify` and `mvn install`. Add the locally installed artifact to your application:

```xml
<dependency>
  <groupId>org.fireflyframework</groupId>
  <artifactId>koinon-sdk</artifactId>
  <version>26.10.2</version>
</dependency>
```

This SDK is installed in your local Maven repository; these commands do not publish to Maven Central. Compilation targets Java 21 bytecode with `-Xlint:all -Werror`; CI has Java 21 and 25 jobs. `tools/sdk/check_java_consumer.py` checks JAR notices, bytecode and an external typed consumer. Package checks do not establish live authenticated API, provider or production acceptance.

## Connect

The caller supplies an API root ending in `/api/v1` and a token supplier. This complete helper only reads the authorized context when explicitly called.

```java
import java.net.URI;
import java.util.function.Supplier;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.ContextResponse;

public final class JavaSdkConnect {
    public static ContextResponse context(URI apiRoot, Supplier<String> accessToken) {
        try (var client = KoinonClient.builder(apiRoot).bearerToken(accessToken).build()) {
            return client.platform().context();
        }
    }
}
```

Use a scoped personal API token or verified OIDC access token issued for the API audience. The supplier runs for every HTTP request, including stream subscription; your application owns sign-in and renewal. Effective access is the intersection of token scopes, resource bounds and the user's current role/membership. The SDK cannot grant access. Personal-token management, corporate identity/profile mapping and OAuth registration administration have ordinary verified-identity requirements; a personal token cannot satisfy those gates merely by carrying a management scope. MCP resource credentials are not API bearer tokens.

Close the client after its outstanding work finishes. It closes an HTTP client it owns. If you inject an `HttpClient`, disable redirects and close it yourself after closing the SDK. Redirects are rejected to keep credentials on the configured origin. Never log bearer tokens, provider credentials or complete credential-bearing requests.

## Practical guides

- [Java quickstart and authentication](../../docs/guides/headless-java.md)
- [Knowledge lifecycle, source files, append and immutable history](../../docs/guides/java-knowledge.md)
- [Conversations, SSE, audit and explicit reviewed actions](../../docs/guides/java-conversations.md)
- [Management, organization directory, async calls and reliability](../../docs/guides/java-operations.md)
- [Embeddings, retrieval, RAG and RLM](../../docs/concepts/knowledge-runtime.md)
- [API permissions and current-role intersection](../../docs/guides/api-permissions.md)
- [Complete typed method reference](../../docs/reference/sdk-api.md)

The [shared operation manifest](../contract/operations.json) defines the canonical API boundary and corresponding methods in each language. Native glossary operations are documented separately. An accessor is not evidence that an optional server module, agent or provider is configured.

## API groups

| Accessor | Purpose |
| --- | --- |
| `platform()` | Authorized context and server capabilities |
| `catalog(tenant)` | Browse, get, create, update, archive, restore and delete supported catalog resources |
| `sources(tenant)` | Stream source-file uploads to an authorized destination |
| `documents(tenant)` | Chunks, originals, revision-bound replacement/reingestion, exact version/extraction/part history |
| `datasets(tenant)` | Schema, table replacement/reingestion, idempotency-bound file append, snapshots/provenance/coordinates |
| `knowledge(tenant)` | Document search, read-only structured queries and authorized asset lineage |
| `knowledgeItems(tenant)` and `knowledgeIntents(tenant)` | Curated items/versions and explicitly reviewed draft/publish/update intents |
| `knowledgeConnections(tenant)` | Supported role descriptors and source/model assignments |
| `providers(tenant)` and `agents(tenant)` | Typed configuration and explicit validation |
| `organizationKnowledge(tenant)` and `organizationChat(tenant)` | Revisioned knowledge behavior and the saved default agent |
| `knowledgeIndexes(tenant)` | Index choices, plans, durable rebuild creation, activation, cancellation and resume |
| `jobs(tenant)` | Authorized processing status and server-job cancellation |
| `chat(tenant)` | Saved conversations/messages, durable runs, events, activity, answer audit and evidence results |
| `chatFolders(tenant)` | Scoped revisioned history folders |
| `chatAttachments(tenant)` | Private upload/extraction/selection/originals and explicit promotion |
| `chatProposals(tenant)` | Read a server diff, then explicitly confirm or cancel |
| `exports(tenant)` and `shares(tenant)` | Bounded review, revision-bound creation, immutable export downloads and authenticated sharing/revocation |
| `evidence(tenant)` | Selected conversation source manifests |
| `profile()` | Global personal profile, preferences and sanitized avatar |
| `organizationPeople(tenant)` | Tenant-bound positions, manager/unit directory, settings, scoped avatars and verified-claim presentation mappings |
| `people(tenant)` | Existing authorized people picker and avatar downloads |
| `members(tenant)` | Membership and role management |
| `invitations(tenant)` and `invitationAccess()` | Organization invitation management and identity-bound acceptance |
| `identity(tenant)` | Guided corporate provider configuration, verification and access mappings |
| `tokens()` and `authorizedApplications()` | Personal-token metadata/issuance/revocation and consenting-user application connections |
| `mcp()` and `mcpOAuthClients(tenant)` | Safe MCP connection metadata and identity-only organization OAuth registration administration |
| `externalReviews(tenant)` and `externalFileReviews(tenant)` | Server-receipt-bound text proposals and staged/chunked/sealed files with exact human decisions |
| `brandingDefaults()` and `organizationBranding(tenant)` | Authorized platform defaults and revisioned organization branding |
| `audit(tenant)` and `configuration(tenant)` | Organization activity records and authorized deployment observations |
| `structuredGlossary(tenant,workspace)` and `structuredAgentGlossary(tenant,workspace)` | Native typed glossary CRUD with exact timestamp preconditions |

## Preserve revisions and outcomes

`fileBatches(tenant)` and `queryBatches(tenant)` provide separate durable intake and independent query lifecycles, private outcomes, revisioned cancellation and explicit receipt reconciliation. Follow the [file intake](../../docs/guides/bulk-intake.md) and [query batch](../../docs/guides/bulk-queries.md) guides. Unknown native outcomes are never replayed automatically; the general jobs API does not cancel these lifecycle jobs.

Request records expose typed `with…` builders. Patch records use `JsonField<T>` to distinguish omission from explicit JSON null. Omission preserves a value; a `clear…` builder serializes null, which the server may reject for that field. For example, organization-source detachment uses explicit `manageLocally=true`, not `clearManagedProviderId()`.

`RequestOptions` is immutable. Document content writes use the current original SHA256 as `If-Match` plus `documentRevision(sourceVersionId,extractionId)` to bind the current ingestion head. Table changes use the exact snapshot ID. Other management writes use their typed expected-revision fields. A conflict requires reading and reviewing current state, not a forced overwrite. Glossary `updatedAt` values remain exact native microsecond strings; do not reformat them before `If-Match`.

Save canonical receipts and caller-supplied idempotency keys for supported operations such as dataset append, private promotion and index creation/resume. Pending or failed intake is not a completed commit. Separate HTTP requests/native sections do not form a bulk transaction. The SDK never retries writes automatically; reconcile unknown outcomes before submitting again.

## Paging, downloads and exact values

`Page<T>` retains server totals, sizes, cursors and actor metadata when available. `Pages.numbered` and `Pages.cursor` lazily call typed page loaders; they do not prefetch or invent pagination for items-only endpoints. Repeated cursors and inconsistent page numbers fail. Native glossary pages can have an unknown total and use limit/offset/hasMore.

Uploads stream stable files. In-memory `BinaryResponse` downloads are bounded to 64 MiB. Larger originals use `downloadOriginal` or `downloadVersionOriginal` with a new target path, explicit byte limit and `RequestOptions`; export streaming uses `downloadDownload`. Incomplete temporary files are removed on failure, existing destinations are not replaced, and a 304 leaves the target untouched.

Business cells remain typed JSON. `ExactValues.decimal(BigDecimal)` preserves decimal scale; `ExactValues.integer(BigInteger)` preserves unsafe integers as strings. Do not reinterpret identifier strings, dates or unknown text automatically. Metadata timestamps use `Instant`; raw JSON is copied defensively.

## Streaming, cancellation and failures

`EventStream<StreamEvent>` is a single-subscriber `Flow.Publisher` and `AutoCloseable`. Request only the demand your consumer can process. Save the last fully processed event ID and reconnect explicitly with `RequestOptions.lastEventId`. Handle `message_reset`, answer policy and terminal events. Closing the stream or cancelling a future releases the HTTP request; use `chat.cancel`, `jobs.cancel` or the appropriate lifecycle API to stop server work. A client disconnect does not prove that a durable run or mutation was rolled back.

`ApiException` exposes HTTP status, native code and support request ID. Async failures can wrap it or network/decoding causes in `CompletionException`; blocking `get` can add `ExecutionException`. Interrupted synchronous calls cancel the request and restore the interrupted flag. Requests default to 30 seconds, with a configurable timeout; active SSE needs an application lifetime and explicit closure. Report safe codes/references rather than raw sensitive response bodies.

An `AnswerAudit` preserves observed generations, sources, private-file revisions, native reads, SQL attempts and RLM tool receipts. Receipt presence is separate from nullable provenance completeness; missing historical observations stay unknown. Imported-snapshot SQL is not a live query to the original database. Model-produced OpenUI is renderer data, never code the SDK executes.

Proposals, curated commits, exports and shares require separate explicit review and exact revisions. External MCP/file decisions additionally require the server's receipt/origin/component-nonce rules; the SDK does not manufacture a human confirmation or expose a generic challenge reader. Registration readiness and one-time confidential-secret handling remain identity-governed. See the practical guides for complete flows.

Copyright 2026 Firefly Software Foundation. Licensed under [Apache-2.0](../../LICENSE); see [NOTICE](../../NOTICE).
