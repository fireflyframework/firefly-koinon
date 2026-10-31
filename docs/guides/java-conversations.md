<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Java conversations and reviewed actions

The Java SDK separates a durable server run from the HTTP connection that observes it. Use [the quickstart](headless-java.md) for client construction and [Knowledge runtime](../concepts/knowledge-runtime.md) for model, embedding, RAG and RLM configuration. A configured agent or saved default does not grant access to knowledge.

## Create and submit a scoped conversation

Use `chat(tenant).threads/get/createThread/update/messages` for saved conversations. `chatFolders(tenant)` provides paginated, revisioned folder operations; thread updates can carry folder and archive metadata. Save canonical IDs and current revisions. A conversation's scope must remain within the caller's current membership and token bounds.

```java
import java.util.List;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaRuns {
    public static ChatRun submit(KoinonClient client, String tenant,
            KnowledgeScope scope, String question, String stableRequestId) {
        var defaults = client.organizationChat(tenant).get(OrganizationChatFilter.empty()
            .withWorkspaceId(scope.workspaceId()).withProjectId(scope.projectId()));
        if (!Boolean.TRUE.equals(defaults.canRun()) || defaults.defaultAgentId() == null) {
            throw new IllegalStateException("An operator must configure an available chat agent");
        }
        var thread = client.chat(tenant).createThread(ThreadInput.empty()
            .withTitle("Knowledge question").withScope(scope));
        return client.chat(tenant).submit(thread.id(), RunInput.empty()
            .withAgentId(defaults.defaultAgentId()).withScope(scope).withMessage(question)
            .withClientRequestId(stableRequestId).withAttachmentIds(List.of()));
    }

    public static ChatRun cancelProcessing(KoinonClient client, String tenant, String runId) {
        return client.chat(tenant).cancel(runId);
    }
}
```

Persist the thread ID and a new caller-generated request ID for each intended submission. Thread creation and run submission are separate writes: in a production application, create/save the thread once, then submit to its saved ID. If a response is lost, reconcile that thread and request before issuing another write. This helper is not a retry loop. `retry(runId)` is an explicit server operation for an eligible failed or cancelled run; it does not make unknown submissions safe to replay.

Private files use `chatAttachments(tenant)`: inspect thread capabilities, upload under the owner/organization/conversation scope, wait for extraction as required, and pass only explicitly selected attachment IDs in `RunInput`. The empty list above selects none. Uploading a file does not automatically include it in a run or publish it as shared knowledge. Promotion is a separate reviewed, revisioned, idempotency-bound action. See [private files in chat](agents.md#private-files-in-chat).

## Consume SSE with bounded demand

The following helper observes an **existing** run. It requests one event at a time, saves a cursor only after processing succeeds, and treats an unexpected stream end as an error. The application supplies a renderer/state reducer and its cursor store. Neither callback should apply proposals or execute model-produced code.

```java
import java.io.IOException;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Flow;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.RequestOptions;
import org.fireflyframework.koinon.sdk.model.StreamEvent;

public final class JavaRunEvents {
    public static void observe(KoinonClient client, String tenant, String runId,
            String lastProcessedId, Consumer<StreamEvent> process,
            Consumer<String> saveCursor) throws Exception {
        var options = RequestOptions.defaults();
        if (lastProcessedId != null) options = options.lastEventId(lastProcessedId);
        var terminal = new CompletableFuture<Void>();
        try (var stream = client.chat(tenant).events(runId, options)) {
            stream.subscribe(new Flow.Subscriber<StreamEvent>() {
                private Flow.Subscription subscription;
                public void onSubscribe(Flow.Subscription value) {
                    subscription = value;
                    value.request(1);
                }
                public void onNext(StreamEvent event) {
                    try {
                        process.accept(event);
                        if (event.id() != null) saveCursor.accept(event.id());
                        if ("completed".equals(event.type())) terminal.complete(null);
                        else if ("failed".equals(event.type()) || "cancelled".equals(event.type())) {
                            terminal.completeExceptionally(new IOException("Run ended: " + event.type()));
                        }
                    } catch (RuntimeException error) {
                        terminal.completeExceptionally(error);
                    }
                    if (terminal.isDone()) subscription.cancel();
                    else subscription.request(1);
                }
                public void onError(Throwable error) { terminal.completeExceptionally(error); }
                public void onComplete() {
                    if (!terminal.isDone()) terminal.completeExceptionally(
                        new IOException("Stream ended without a terminal event"));
                }
            });
            try {
                terminal.get(180, TimeUnit.SECONDS);
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
                throw error;
            }
        }
    }
}
```

Each stream accepts one subscriber. Closing it, cancelling its subscription or timing out the wait releases the connection; it does **not** cancel durable processing. Call the explicit `chat(tenant).cancel(runId)` operation when the user wants processing to stop. After an intentional reconnect, open a new stream with the last fully processed event ID. Reconnection is not automatic; design cursor persistence and presentation updates to tolerate replay after a local failure.

On `message_reset`, replace the previous partial answer state before processing new deltas. Handle typed `answerPolicy`, citations, presentation and tool-activity data in `StreamEvent.data()`. A `review_required` policy is a request for a separate human decision, not permission to apply a proposal. Tool activity exposes safe summaries and authorized evidence references; hidden reasoning and tool arguments are not a public trace. OpenUI artifacts are data for registered renderers, never JavaScript/HTML to execute blindly.

## Read evidence and audit

After a run, `chat(tenant).audit(runId)` returns its owner-authorized `AnswerAudit`; `activities(runId)` pages saved tool activity, and `result(runId,resultId)` reads an authorized stored payload referenced by that activity. `messages(threadId)` reads saved messages independently of a live stream. `evidence(tenant)` exposes selected conversation manifests. None of these methods grants another conversation owner's access.

Keep these audit distinctions in your application:

- Receipt presence and `sourceProvenanceComplete()` are separate. Null completeness means historical information was not recorded.
- Source versions, private-file SHA/revisions and imported table snapshots identify what was observed. Current availability is checked separately; do not rewrite historical identity to the current head.
- SQL attempts contain the actual submitted statement, execution outcome and referenced snapshots. DuckDB database/catalog context describes imported-snapshot execution, not proof of a live query to the original connection.
- A generation without a recorded end time is not evidence of completion. A terminal SSE event also does not manufacture missing source provenance or provider-acceptance proof.

`audit(tenant).list(AuditFilter...)` is the separate organization activity log and requires organization-level `audit:read`. Its purpose differs from an answer's evidence audit; do not expose either log simply because a user can read a catalog asset.

## Keep review and execution separate

The next helpers deliberately separate preparation from an explicit decision. Show the server-returned messages, sources, omissions, recipient policy, expiry and revision to a person. Call a creation helper only with the exact review they approved.

```java
import java.util.List;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaReviewedActions {
    public static ExportReview reviewExport(KoinonClient client, String tenant,
            String threadId, List<String> selectedMessageIds) {
        return client.exports(tenant).review(ConversationExportInput.empty()
            .withKind(ConversationExportInputKind.CONVERSATION)
            .withFormat(ConversationExportInputFormat.MARKDOWN)
            .withThreadId(threadId).withMessageIds(selectedMessageIds).withIncludeEvidence(true));
    }

    public static org.fireflyframework.koinon.sdk.model.Export createReviewedExport(
            KoinonClient client, String tenant, ExportReview reviewed, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Explicit confirmation required");
        return client.exports(tenant).create(ExportCreate.empty()
            .withReviewId(reviewed.id()).withExpectedRevision(reviewed.revision()));
    }

    public static ShareReview reviewShare(KoinonClient client, String tenant,
            String threadId, List<String> selectedMessageIds) {
        return client.shares(tenant).review(ShareReviewInput.empty()
            .withThreadId(threadId).withMessageIds(selectedMessageIds));
    }

    public static Share createReviewedShare(KoinonClient client, String tenant,
            ShareReview reviewed, int expiresInHours, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Explicit confirmation required");
        return client.shares(tenant).create(ShareCreate.empty()
            .withReviewId(reviewed.id()).withExpectedRevision(reviewed.revision())
            .withRecipientPolicy(reviewed.recipientPolicy()).withExpiresInHours(expiresInHours));
    }

    public static CatalogProposal confirmReviewedProposal(KoinonClient client, String tenant,
            String runId, String proposalId, long reviewedRevision, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Explicit confirmation required");
        return client.chatProposals(tenant).confirm(runId, proposalId,
            ProposalConfirmation.empty().withConfirm(true).withExpectedRevision(reviewedRevision));
    }
}
```

A local boolean represents your application's explicit human decision; it is not a new authority claim and cannot bypass server checks. Fetch a catalog proposal through `chatProposals(tenant).get` and present its actual diff before using the confirmation helper. Revision conflicts require a fresh review. Never chain review and confirm automatically or confirm from an SSE callback.

Exports require the appropriate `exports:read/write` scopes; shares require `shares:read/write` plus their dependency scopes and current owner/resource authority. `exports(tenant).get/list/cancel` manages an export's state; its download reads stored immutable bytes without rerunning SQL. Use bounded `downloadDownload` for a file destination. `shares(tenant).get/list/revoke` manages authenticated conversation shares; recipients still need the current source ACL. A share is not a public anonymous URL.

External text/file review and MCP registration have additional origin, component-nonce and credential-type boundaries. Use the [MCP knowledge-management guide](mcp-knowledge-management.md), [registered applications](register-applications.md) and [exports and sharing guide](exports-sharing.md) rather than treating ordinary API access as a substitute for user consent.
