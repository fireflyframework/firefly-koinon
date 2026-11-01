<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Java SDK

Build a Java application or service against the same typed, authorized API used by the koinon interface. The SDK requires **Java 21 or later**, uses the JDK HTTP client and Jackson, and does not depend on the backend or a web framework. It provides synchronous methods, `CompletableFuture` methods, bounded file downloads and demand-driven SSE streams.

## Work through the tutorial

Start here when you have an API address and an account but have not written an integration yet. The first program establishes authentication, checks the available organization context, and pages through documents. It makes no changes. After it works, keep the same client configuration for [knowledge](java-knowledge.md), [conversations](java-conversations.md), and [administration](java-operations.md).

Use the resource IDs from your first catalog read in the remaining chapters. Each chapter introduces the permissions, inputs and response fields needed for its operations.

[Download the complete Java 21+ tutorial source and build instructions](../examples/java/README.md). The files include imports and entry points. Each chapter's default entry point reads existing state; write helpers are separate functions that your application calls after its own explicit decision. Keep all files for the selected language together.

## Prepare the deployment and credential

Ask your operator for an authorized API root, an organization, and a workspace you can read. Start with a credential whose scope includes `catalog:read` and whose resource bounds admit that workspace. Do not request every management scope merely to make the first request succeed.

| Value | Where it comes from | How the program uses it |
| --- | --- | --- |
| `KOINON_API_URL` | Your deployment operator | API root ending in `/api/v1`, without a token in the URL. |
| `KOINON_TOKEN` | A current API-audience OIDC access token or a scoped personal API token | The callback supplies it afresh for each request. |
| `KOINON_TENANT_ID` | The organization's canonical ID in the current context | Every tenant operation uses this exact organization. |
| `KOINON_WORKSPACE_ID` | An authorized workspace returned by the API | Catalog and knowledge filters stay inside this destination. |

An OIDC access token comes from your host's approved identity flow. This tutorial does not implement that flow or ask for a refresh token. For a personal token, sign in through the ordinary account flow, review its permitted scopes and resource bounds, and save its one-time secret privately. An existing PAT cannot create another PAT. Never substitute a model-provider key, an ID token, or an MCP resource token.

Set the variables through your shell's secure environment mechanism or secret manager. Avoid pasting live credentials into an example file, a terminal transcript, a URL, or a support ticket. A long-running host should renew its access token before returning it from the callback; replacing an expired token is the host's responsibility.

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
  <version>26.11.3</version>
</dependency>
```

Match the dependency version to the SDK version you installed locally. The POM targets Java 21 and checks all compiler warnings. Set your application's compiler target to Java 21 or later as well. The SDK JAR is also available from [GitHub Releases](https://github.com/fireflyframework/firefly-koinon/releases), alongside its checksums.

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

## Understand the first response

Run the startup program only after choosing the deployment and credential above. The context response identifies the current subject, available organizations, memberships, workspaces, and applicable permissions. Select IDs from that response rather than displaying a guessed organization or treating a URL parameter as a grant. In an application, keep that context with the authenticated session and discard it when the identity changes.

The catalog request returns a typed page. `items` contains the current authorized rows; `page`, `page_size` or `size`, `pages`, and `total` describe pagination when the endpoint supplies them. The helper asks for another server page lazily. It does not fetch a large list and slice it locally. An empty list can be a legitimate empty scope; it is not an invitation to remove the workspace filter.

The printed IDs and names are the program's expected output. They are resource identities for later calls, not sample fixture IDs you should hardcode. Retain a selected document or dataset ID when moving to the next chapter. Keep names as labels, since renaming an asset does not change its identity.

If the first call returns `401`, repair the host's token acquisition or expiry handling before continuing. If it returns `403`, compare the current role, requested scopes, resource bounds, and credential type. A wider token cannot repair a missing role. For a timeout or protocol error, retain only safe status and request-reference metadata; never print the token or a whole private response body.

The SDK does not renew credentials, create a sign-in session, or reconnect a stream automatically. Keeping those responsibilities in the host lets a web application, command-line tool, and scheduled service use the same API without sharing browser cookies or credentials accidentally.

## Choose a workflow

| Task | Guide |
| --- | --- |
| Create destinations, upload files, change content, append a dataset file, inspect immutable versions and lineage | [Knowledge and files](java-knowledge.md) |
| Submit a scoped run, consume SSE, inspect answer audit and review proposals, exports or shares | [Conversations and reviewed actions](java-conversations.md) |
| Configure agents and knowledge behavior, manage organization metadata, use async calls and handle errors or bounded downloads | [Operations and reliability](java-operations.md) |
| Understand embeddings, retrieval, RAG and RLM behavior before choosing configuration | [Knowledge runtime](../concepts/knowledge-runtime.md) |
| Find every method, input record and response type | [API and SDK reference](../reference/sdk-api.md) |

Each guide uses existing typed methods and keeps mutations in explicitly called helpers. Choose the destination and current permission scope before calling a write helper. The SDK has no automatic write retry, forced revision overwrite, background batch transaction or model-readiness guarantee.
