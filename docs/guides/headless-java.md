<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Java SDK

Build a Java application or service against the same typed, authorized API used by the koinon interface. The SDK requires **Java 21 or later**, uses the JDK HTTP client and Jackson, and does not depend on the backend or a web framework. It provides synchronous methods, `CompletableFuture` methods, bounded file downloads and demand-driven SSE streams.

## Install from the repository

From the repository root, with JDK 21 or later and Maven available:

```sh
mvn --batch-mode --no-transfer-progress -f sdk/java/pom.xml verify
mvn --batch-mode --no-transfer-progress -f sdk/java/pom.xml install
```

Add the locally installed artifact to your application:

```xml
<dependency>
  <groupId>org.fireflyframework</groupId>
  <artifactId>koinon-sdk</artifactId>
  <version>26.10.0-alpha.2</version>
</dependency>
```

This is a development artifact; local installation does not publish it to Maven Central. The POM compiles with `--release 21`, all compiler warnings enabled and warnings treated as errors. CI has Java 21 and 25 jobs. Your application's compiler target must also be Java 21 or later. Package checks, hosted CI results and live deployment acceptance are separate evidence.

## Authenticate and browse

Set `KOINON_API_URL` to the API root ending in `/api/v1`, `KOINON_TOKEN` to your credential, and `KOINON_TENANT_ID` and `KOINON_WORKSPACE_ID` to authorized identifiers. Store credentials in your application's secret store. Do not put them in source code, exception logs or a URL.

Use a scoped personal API token or a verified OIDC access token issued for the API audience. A token's authority is the intersection of its scopes, its saved organization/workspace/asset bounds, and the user's current permissions. A wide token does not elevate the user's role. A role downgrade or resource departure can make a later request fail even after an earlier request succeeded. See [API permissions and writes](api-permissions.md) for the role matrix and scope dependencies.

Save the following complete example as `JavaQuickstart.java`. Its `main` only reads the authorized context and document catalog; it does not upload, generate an answer or change configuration.

```java
import java.net.URI;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.Pages;
import org.fireflyframework.koinon.sdk.model.CatalogFilter;

public final class JavaQuickstart {
    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Set " + name);
        }
        return value;
    }

    public static void main(String[] args) {
        try (var client = KoinonClient.builder(URI.create(required("KOINON_API_URL")))
                .bearerToken(() -> required("KOINON_TOKEN")).build()) {
            client.platform().context();
            String tenant = required("KOINON_TENANT_ID");
            var filter = CatalogFilter.empty()
                .withWorkspaceId(required("KOINON_WORKSPACE_ID"))
                .withKind("document").withPageSize(25).withSort("name").withOrder("asc");
            for (var entry : Pages.numbered(
                    page -> client.catalog(tenant).list(filter.withPage(page)), 1)) {
                System.out.println(entry.id() + " " + entry.name());
            }
        }
    }
}
```

The supplier is called for each HTTP request, including stream subscription. In a long-running service, replace the environment lookup with your identity system's access-token supplier and renewal policy. The SDK does not implement sign-in, token refresh or role assignment. Personal-token creation and corporate identity/profile-mapping administration require the appropriate ordinary verified identity; a personal token cannot bootstrap those privileges. MCP resource credentials are not ordinary API bearer tokens.

The client is `AutoCloseable`. It closes its own HTTP client and outstanding requests. If you inject an `HttpClient`, keep redirects disabled and close it yourself after closing the SDK. Redirect rejection keeps bearer credentials on the configured API origin.

## Choose a workflow

| Task | Guide |
| --- | --- |
| Create destinations, upload files, change content, append a dataset file, inspect immutable versions and lineage | [Knowledge and files](java-knowledge.md) |
| Submit a scoped run, consume SSE, inspect answer audit and review proposals, exports or shares | [Conversations and reviewed actions](java-conversations.md) |
| Configure agents and knowledge behavior, manage organization metadata, use async calls and handle errors or bounded downloads | [Operations and reliability](java-operations.md) |
| Understand embeddings, retrieval, RAG and RLM behavior before choosing configuration | [Knowledge runtime](../concepts/knowledge-runtime.md) |
| Find every method, input record and response type | [API and SDK reference](../reference/sdk-api.md) |

Each guide uses existing typed methods and keeps mutations in explicitly called helpers. Choose the destination and current permission scope before calling a write helper. The SDK has no automatic write retry, forced revision overwrite, background batch transaction or model-readiness guarantee.
