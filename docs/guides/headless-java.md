# Java: paging, intake and streamed answers

The Java 21 SDK uses the JDK HTTP client and Jackson. Build and install from the trusted repository with `mvn -f sdk/java/pom.xml install`, then use `org.fireflyframework:koinon-sdk:26.10.0-alpha.1` in your application's Maven dependencies. This installs a development artifact in your local repository; it does not publish to Maven Central.

Set `KOINON_API_URL` to the root ending in `/api/v1`, `KOINON_TOKEN` to a scoped personal or API-audience OIDC access token, and `KOINON_TENANT_ID` and `KOINON_WORKSPACE_ID` to authorized identifiers. Replace the environment token supplier with your identity provider's renewal supplier in a long-running service. Each request obtains a fresh value from the supplier.

Save this as `HeadlessKnowledge.java` inside your Java project. Its `main` method only reads the authorized context and browses documents. Invoke upload and answer helpers explicitly when your product has the destination and scope selected.

```java
import java.io.IOException;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Flow;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.Pages;
import org.fireflyframework.koinon.sdk.model.*;

public final class HeadlessKnowledge {
    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) throw new IllegalStateException("Set " + name);
        return value;
    }

    public static void browse(KoinonClient client, String tenant, String workspace) {
        var filter = CatalogFilter.empty().withWorkspaceId(workspace).withKind("document")
            .withPageSize(25).withSort("name").withOrder("asc");
        for (var document : Pages.numbered(page -> client.catalog(tenant).list(filter.withPage(page)), 1)) {
            System.out.println(document.id() + " " + document.name());
        }
    }

    public static void uploadFiles(KoinonClient client, String tenant, String workspace,
            String project, String collection, List<Path> files, UploadMode mode,
            Consumer<UploadResponse> acceptedReceipt) throws IOException {
        if (files.isEmpty() || files.size() > 16) throw new IllegalArgumentException("Choose 1 to 16 files");
        for (Path file : files) {
            if (!Files.isRegularFile(file) || Files.size(file) > 32L * 1024 * 1024) {
                throw new IllegalArgumentException("Choose regular files up to 32 MiB");
            }
        }
        for (Path file : files) {
            var receipt = client.sources(tenant).upload(new SourceUpload(file,
                "application/octet-stream", workspace, project, collection, mode));
            acceptedReceipt.accept(receipt);
        }
    }

    public static AnswerAudit ask(KoinonClient client, String tenant,
            KnowledgeScope scope, String question) throws Exception {
        var settings = client.organizationChat(tenant).get(OrganizationChatFilter.empty()
            .withWorkspaceId(scope.workspaceId()).withProjectId(scope.projectId()));
        if (!Boolean.TRUE.equals(settings.canRun()) || settings.defaultAgentId() == null) {
            throw new IllegalStateException("An operator must configure the organization's chat agent");
        }
        var thread = client.chat(tenant).createThread(ThreadInput.empty()
            .withTitle("Knowledge question").withScope(scope));
        var run = client.chat(tenant).submit(thread.id(), RunInput.empty()
            .withAgentId(settings.defaultAgentId()).withMessage(question).withScope(scope)
            .withClientRequestId(UUID.randomUUID().toString()).withAttachmentIds(List.of()));
        var completed = new CompletableFuture<Void>();
        try (var stream = client.chat(tenant).events(run.runId())) {
            stream.subscribe(new Flow.Subscriber<StreamEvent>() {
                private Flow.Subscription subscription;
                public void onSubscribe(Flow.Subscription value) {
                    subscription = value;
                    value.request(1);
                }
                public void onNext(StreamEvent event) {
                    System.out.println(event.id() + " " + event.type());
                    if ("completed".equals(event.type())) completed.complete(null);
                    else if ("failed".equals(event.type()) || "cancelled".equals(event.type())) {
                        completed.completeExceptionally(new IOException("Run ended: " + event.type()));
                    }
                    if (completed.isDone()) subscription.cancel();
                    else subscription.request(1);
                }
                public void onError(Throwable error) { completed.completeExceptionally(error); }
                public void onComplete() {
                    if (!completed.isDone()) completed.completeExceptionally(
                        new IOException("Stream ended without a completed event"));
                }
            });
            completed.get(180, TimeUnit.SECONDS);
        }
        return client.chat(tenant).audit(run.runId());
    }

    public static void main(String[] args) {
        try (var client = KoinonClient.builder(URI.create(required("KOINON_API_URL")))
                .bearerToken(() -> required("KOINON_TOKEN")).build()) {
            client.platform().context();
            browse(client, required("KOINON_TENANT_ID"), required("KOINON_WORKSPACE_ID"));
        }
    }
}
```

The client and stream are `AutoCloseable`. Each event requests the next item only after processing the previous one. Timeout or stream closure releases the HTTP connection; it does not cancel the server's durable run. When a user requests cancellation, call `client.chat(tenant).cancel(runId)`. To resume intentionally, pass `RequestOptions.defaults().lastEventId(lastProcessedId)` to `events`. Replace partial presentation state on `message_reset`.

`uploadFiles` invokes a receipt consumer after each accepted item, so your application can record partial success before continuing. Choose `UploadMode.DOCUMENT` or `UploadMode.DATASET` for the supported intake. Keep the files stable during upload. This sequential client loop supplies neither a durable batch queue nor automatic retry after an unknown outcome. The server enforces its own intake and authorization limits.

The SDK also provides asynchronous resource methods returning `CompletableFuture<T>`. Inspect messages with `client.chat(tenant).messages(threadId)` and saved tool payloads with `.result(runId, resultId)`. The [typed audit](agents.md#read-the-audit-without-the-frontend) keeps admitted scope, observed reads and nullable historical fields separate. See [reviewed exports and shares](exports-sharing.md) and the [complete method reference](../reference/sdk-api.md).
