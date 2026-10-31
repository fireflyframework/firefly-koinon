<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Java operations and reliability

Start with the [Java SDK quickstart](headless-java.md). Use the administrative APIs to configure your organization, manage members and monitor jobs. Each operation checks your current permissions and selected scope.

## Work from observations to deliberate changes

Start by reading current context and selecting the organization you administer. Distinguish organization authority from workspace administration: a workspace role cannot be widened by requesting an organization-management scope. For each task, use the [permission matrix](api-permissions.md) to choose an ordinary identity or a permitted bounded API credential before constructing an input.

[Download the complete administration source](../examples/java/README.md). Its default entry point reads only the current account's position in the selected organization, using the self/profile boundary. Provider, member, agent, knowledge-settings and index helpers are separate operations; importing the file or constructing a client does not execute them.

For a production host, build an administrative screen or command in two stages: load and display the current state, then submit the reviewed typed change after a person chooses it. Retain the reviewed revision, operation identity and safe response metadata. Do not turn a permission failure into a request for every available scope or retry an unknown write automatically.

## Run the read-only chapter

Compile the complete classes using the Java source instructions before running this read-only command. `KOINON_SDK_CLASSPATH` contains the verified SDK and its declared Jackson dependencies. [Complete source and build instructions](../examples/java/README.md) include [the entry-point file](../examples/java/TutorialMain.java). Use the organization already selected in `KOINON_TENANT_ID`. Keep credentials in the approved environment rather than adding them to these commands.

```sh
java -cp "classes:$KOINON_SDK_CLASSPATH" TutorialMain people
```

The result prints the current tenant position ID and job title. A missing assignment can have a null ID; the GET does not create it. If authorization fails, return to the setup chapter and inspect current context/scopes instead of broadening the request. The remaining helpers define the intended mutations, but this command does not invoke them.

## Configure the organization deliberately

| Area | Java accessor and workflow | Permission boundary |
| --- | --- | --- |
| Providers and agents | `providers(tenant).create/update/validate`, `agents(tenant).list/create/update/validate`; read provider observations through `configuration(tenant).get` | Organization-scoped `providers:write` or `agents:write`; current operator/administrator authority |
| Source/model assignments | `knowledgeConnections(tenant).roles/list/get/create/update/remove` | `sources:configure`; use supported role descriptors rather than inventing connection roles |
| Organization knowledge behavior | `organizationKnowledge(tenant).get/update` | `settings:write`; current revision and organization authority |
| Default chat agent | `organizationChat(tenant).get/update` | Organization-level `agents:write`; current revision; selection does not grant knowledge access |
| Native indexes | `knowledgeIndexes(tenant).choices/choice/plan/create/get/list/activate/cancel/resume` | `indexes:manage`; review the plan and current revision; retain create/resume idempotency keys |
| Processing jobs | `jobs(tenant).list/get/cancel` | Current job-resource visibility and applicable `jobs:manage` or compatible ingestion-write authority |
| Members and invitations | `members(tenant).list/add/update/remove`, `invitations(tenant).list/create/revoke` | Organization membership-management authority; a position/title is never a role grant |
| Corporate identity | `identity(tenant).list/create/get/update/test/testStatus/groups/mappings/createMapping/updateMapping/removeMapping/activate/disable` | Ordinary verified identity plus organization `identity:manage`; provider/group access is limited to the configured server capability |
| Personal tokens | `tokens().scopes/list/create/revoke` | Verified interactive token owner; personal tokens cannot manage other tokens |
| Authorized applications | `authorizedApplications().list/get/revoke` | The current consenting user; revocation is an explicit choice |
| MCP registrations | `mcpOAuthClients(tenant).readiness/list/create/get/update/rotateSecret` | Ordinary verified organization identity administrator; personal/application credentials cannot administer registrations |
| Deployment observations | `configuration(tenant)` and `platform().context()` | Authorized observations, not a credential or permission bootstrap |

The [permission guide](api-permissions.md) lists scope dependencies and current-role capabilities. Management scopes are organization-wide and cannot be disguised as workspace-restricted grants. Use the generated reference for the exact input variant and revision/idempotency parameters; it is the complete method inventory.

```java
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaOrganizationSettings {
    public static ModelProvider renameProvider(KoinonClient client, String tenant,
            String providerId, String name) {
        return client.providers(tenant).update(providerId, ProviderInput.empty().withName(name));
    }

    public static OrganizationChatSettings setDefaultAgent(KoinonClient client,
            String tenant, OrganizationChatSettings reviewed, String agentId) {
        return client.organizationChat(tenant).update(OrganizationChatSettingsInput.empty()
            .withExpectedRevision(reviewed.revision()).withDefaultAgentId(agentId));
    }

    public static OrganizationKnowledgeSettings setDocumentMode(KoinonClient client,
            String tenant, OrganizationKnowledgeSettings reviewed, KnowledgeAnswerMode mode) {
        return client.organizationKnowledge(tenant).update(OrganizationKnowledgeSettingsInput.empty()
            .withExpectedRevision(reviewed.revision())
            .withDocuments(reviewed.documents().withAnswerMode(mode))
            .withStructured(reviewed.structured()));
    }
}
```

Obtain and display the current settings before calling a helper. Pass the reviewed revision rather than silently fetching a new one immediately before overwriting. `clearDefaultAgentId()` explicitly removes the chat default. `KnowledgeAnswerMode.RAG` and `RLM` choose supported policy values; neither provisions an embedding model, agent, index or provider automatically. Use [Knowledge runtime](../concepts/knowledge-runtime.md) for their prerequisites, source-selection behavior and configuration boundaries.

Provider credential variants and agent inputs are typed. Omitted credentials retain their value; explicit null can remove supported credentials. Keep secrets in the deployment's supported secret configuration, handle one-time secret returns privately, and never put whole request records, bearer tokens or provider credentials in logs. Explicit validation/test operations may require the deployment's configured external systems; configuration serialization and Java compilation alone prove neither connectivity nor answer quality.

For native indexes, read `choices` and `plan`, present the proposed scope and effects, then explicitly create the rebuild. Follow durable state before activating or resuming; keep its revision and idempotency key. Cancelling a request future does not cancel a server rebuild. Use the index or job cancellation API for server work. Do not fabricate recovery commands from incomplete status.

## Configure a provider and an agent in order

Read the current provider observations through configuration before creating another provider. Select a supported provider kind and API variant, the deployment-approved endpoint, and actual model IDs. Supply real credentials through your approved secret source only when the provider requires them. The typed `ProviderInput` in the complete source accepts the reviewed configuration; it does not contain a sample provider key, discover secret values, or prove connectivity. Never print the input or a one-time secret return.

Call `providers(tenant).create` only after that configuration is reviewed. Save the returned provider ID and inspect its observed availability. A separate validate operation can contact the configured external system and must be run intentionally. Successful configuration serialization is different from a successful provider test, and both are different from a completed answer.

Next build a typed agent input using that actual provider ID, a model ID available there, a chosen knowledge scope and only the tools needed for the task. The complete source's agent helper keeps these inputs explicit. Call `agents(tenant).create` with `agents:write`, retain its ID, and inspect its validation/availability. Selecting tools or an agent does not grant the agent more knowledge access than the current caller.

Finally read the organization's chat settings, display the selected default agent and revision, and update that default only after a person confirms it. Omitting a patch field preserves it; explicit null clears a field only where the endpoint permits it. Preserve unrelated settings. Re-read after a revision conflict instead of taking a new revision and silently replaying the old decision.

This complete class keeps provider configuration, a bounded reader agent and a member-access update as separate confirmed operations. Inputs must come from your authorized operator workflow; a local boolean does not override the server's current permission checks. Retain each canonical response before moving to the next operation.

```java
import java.util.List;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaAdministration {
    private JavaAdministration() {}

    public static ModelProvider createProvider(KoinonClient client, String tenant,
            ProviderInput reviewed, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Review provider configuration");
        return client.providers(tenant).create(reviewed);
    }

    public static AgentConfiguration createReader(KoinonClient client, String tenant,
            String providerId, String modelId, KnowledgeScope scope, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Review agent model, tools and scope");
        return client.agents(tenant).create(AgentInput.empty()
            .withName("Knowledge reader").withProviderId(providerId).withModelId(modelId)
            .withScope(scope).withTools(List.of(AgentTool.SEARCH_KNOWLEDGE,
                AgentTool.INSPECT_SCHEMA, AgentTool.QUERY_DATASET)).withEnabled(true));
    }

    public static Membership updateMember(KoinonClient client, String tenant,
            String memberId, MemberUpdate reviewed, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Review the member and access change");
        return client.members(tenant).update(memberId, reviewed);
    }
}
```

## Choose RAG or RLM and plan index work

Read `organizationKnowledge(tenant).get` before changing document behavior. Copy its document and structured sections into the typed settings input, change only the chosen supported value, and send the reviewed revision. The complete source demonstrates changing document `answer_mode` while preserving all other document parameters and the structured settings. Use `settings:write` and current organization authority.

RAG retrieves an admitted evidence subset for an answer. RLM uses the configured bounded native exploration policy. Neither setting provisions a provider, changes a source connection, imports an embedding model, or proves a successful run. Inspect the [knowledge runtime prerequisites](../concepts/knowledge-runtime.md) before enabling either mode, and use the answer audit to distinguish recorded retrieval and RLM actions from missing historical metadata.

For an embedding rebuild, read available choices and call `knowledgeIndexes(tenant).plan` with the intended workspace/domain and actual provider/model IDs. Display the plan's scope and effects first. Creating with `knowledgeIndexes(tenant).create` is a separate action requiring `indexes:manage` and a stable caller-owned idempotency key. Retain the returned index/job identity and inspect `jobs(tenant).get` or the index state before assuming processing finished.

Activation is another explicit transition. Use the current revision and expected active index/connection preconditions from the reviewed state. Canceling HTTP does not cancel a server rebuild. Use its explicit cancellation operation when requested; resume requires its own current preconditions and stable request identity. A failed or pending state is not permission to discard history or invent a recovery action.

## People, profiles and organization structure

`profile()` manages the authenticated user's global profile, locale/preferences and sanitized avatar. `organizationPeople(tenant)` manages per-organization position, units, manager relationships, directory settings and verified-claim presentation mappings. These are separate surfaces: a global display-name change does not edit an organization position, and a job title or reporting line never grants access.

```java
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaOrganizationDirectory {
    public static OrganizationPersonPage browse(KoinonClient client, String tenant,
            String authorizedWorkspace, String query, int page) {
        return client.organizationPeople(tenant).list(OrganizationPeopleFilter.empty()
            .withWorkspaceId(authorizedWorkspace).withQ(query).withPage(page).withPageSize(25));
    }

    public static OrganizationPerson changeLocalTitle(KoinonClient client, String tenant,
            OrganizationPerson reviewed, String title) {
        if (reviewed.id() == null) throw new IllegalArgumentException("Create an assignment first");
        return client.organizationPeople(tenant).update(reviewed.id(), OrganizationPersonPatch.empty()
            .withExpectedRevision(reviewed.revision()).withJobTitle(title));
    }
}
```

The directory defaults to organization administrators. An explicitly enabled shared-workspace view still needs the authorized workspace and current shared membership; a private workspace does not expose all organization members. Use `me` for self, paginated `list/reports/units` for authorized projections, and scoped `avatar`/`downloadAvatar` for photos. Do not infer hidden managers, units or counts from omitted/nullable fields.

A person can have a visible profile but no organization assignment: `id()` is null and `revision()` is zero. A GET does not create a row. An authorized administrator uses `create(OrganizationPersonCreate...)` with the emitted opaque `profileId` from the authorized picker. Unit creation/update/deletion uses typed inputs and current revisions; deletion checks occupied units. Use bounded pages and explicit parent filters to traverse a tree; do not recursively fetch the whole organization without a user-selected scope.

Position edits require tenant-wide `members:write`, not merely workspace-administrator status. Mappings require an ordinary verified identity and `identity:manage`; personal tokens are rejected even if they have that management scope. Mapping fields use only verified current login claims actually supplied by the configured provider. They do not call arbitrary cloud directories, add consent scopes, accept browser-supplied claims or modify membership grants.

For provider-managed fields, the server enforces source ownership. `manageLocally=true` explicitly detaches the source under the current revision. Explicit `managedProviderId` reattachment requires both organization `members:write` and ordinary-identity `identity:manage`, plus an active configured mapping; current values stay pending until a later verified login. Omit `managedProviderId` to preserve it. Null/empty is rejected; do not use the generic `clearManagedProviderId()` serializer for detachment or combine reattachment with `manageLocally`. See [People and organization](people-and-organization.md) for the complete administration policy.

## Async calls, cancellation and errors

Every resource operation has a corresponding `...Async` form returning `CompletableFuture<T>`. Keep the original returned future if you need to cancel its HTTP request; cancelling a dependent stage from `thenApply` or `whenComplete` is not a server cancellation operation. Keep the client open until outstanding work is complete.

```java
import java.time.Duration;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import org.fireflyframework.koinon.sdk.ApiException;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.RequestOptions;
import org.fireflyframework.koinon.sdk.model.CatalogEntry;
import org.fireflyframework.koinon.sdk.model.CatalogFilter;
import org.fireflyframework.koinon.sdk.model.Page;

public final class JavaAsyncReads {
    public static CompletableFuture<Page<CatalogEntry>> load(KoinonClient client,
            String tenant, String workspace) {
        var pending = client.catalog(tenant).listAsync(CatalogFilter.empty()
            .withWorkspaceId(workspace).withPage(1).withPageSize(25),
            RequestOptions.defaults().timeout(Duration.ofSeconds(45)));
        pending.whenComplete((page, error) -> {
            if (error == null) System.out.println("Loaded " + page.items().size() + " entries");
            else report(error);
        });
        return pending;
    }

    private static void report(Throwable error) {
        Throwable cause = error;
        while (cause instanceof CompletionException && cause.getCause() != null) {
            cause = cause.getCause();
        }
        if (cause instanceof ApiException problem) {
            System.err.println("HTTP " + problem.status() + " code=" + problem.code()
                + " request=" + problem.requestId());
        } else {
            System.err.println("Request failed: " + cause.getClass().getSimpleName());
        }
    }
}
```

The caller can cancel the original `pending` future with `cancel(true)`. That releases the request; an accepted server mutation, run, export or job can still exist. A network failure after submission is an unknown outcome, not evidence of rollback. Persist operation IDs/idempotency keys and reconcile before any further write. The SDK never retries writes automatically.

Requests default to a 30-second timeout and the client connect timeout defaults to 10 seconds. `RequestOptions.timeout` changes a request's bound; it is not a server-work deadline. An established SSE stream needs its own application lifetime and explicit closure. Interrupted synchronous calls cancel their pending request and restore the thread's interrupted flag. Async failures can wrap `ApiException` or network/decoding causes in `CompletionException`; a blocking `get` can additionally wrap them in `ExecutionException`.

| Outcome | Application action |
| --- | --- |
| 401 | Obtain a valid unexpired credential through the identity system; do not log it |
| 403 | Check current role, token scope, resource bounds and identity type; do not widen access automatically |
| Revision conflict or precondition failure | Read current state, show changed effects, and obtain a fresh decision |
| Timeout, disconnect or cancellation after a write | Reconcile the saved operation and canonical state before deciding what to do next |
| Size/decoding/protocol error | Retain the support request reference and safe metadata; do not print sensitive response bodies |

## Bound file downloads and preserve exact values

In-memory `BinaryResponse` downloads are bounded to 64 MiB. For larger originals, use the streaming file helper with an explicit maximum and a new destination path. The file is not a model-generated executable.

```java
import java.nio.file.Path;
import org.fireflyframework.koinon.sdk.FileDownload;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.RequestOptions;

public final class JavaOriginalDownload {
    public static FileDownload download(KoinonClient client, String tenant,
            String documentId, Path newTarget, String previousEtag) {
        var options = RequestOptions.defaults();
        if (previousEtag != null) options = options.header("If-None-Match", previousEtag);
        return client.documents(tenant).downloadOriginal(documentId, newTarget,
            256L * 1024 * 1024, options);
    }
}
```

A successful file response includes byte count, content type, filename and ETag. The helper removes incomplete temporary files after failure and never replaces an existing destination. A conditional 304 leaves it untouched; inspect `notModified()` before treating the path as a new file. Exact document-version downloads use `downloadVersionOriginal`; exports use `downloadDownload`; directory avatars use the scoped `downloadAvatar`. Server-side authorization and retention still apply to historical bytes.

Use typed DTOs and `JsonField<T>` builders for patch omission versus explicit null. Server semantics decide which fields can be cleared; a generic serializer is not permission to clear every field. Keep decimal/integer business cells as exact JSON values: `ExactValues.decimal(BigDecimal)` preserves decimal scale and `ExactValues.integer(BigInteger)` preserves unsafe integers as strings. Do not reinterpret identifier/date strings as numbers. Retain native microsecond glossary `updatedAt` strings for their exact `If-Match`; `structuredGlossary` and `structuredAgentGlossary` have native limit/offset pages and do not count as canonical contract operations.

See the [method reference](../reference/sdk-api.md) for exact typed signatures and the [Java conversations guide](java-conversations.md) for stream closure, evidence and explicit review flows.

## Manage access separately from presentation

List members in the authorized organization/workspace and select the exact membership to change. A typed member update changes `role` or `active`; it is an access decision requiring `members:write` and current membership-management authority. Review the affected person, scope and change before sending it. A title, department, unit, reporting line or avatar is presentation data and never grants a role.

Use `organizationPeople(tenant).me` for the current tenant position and `profile().get` for the personal account. The directory has its own visibility setting and current membership guard; a shared-workspace projection does not expose the entire organization. A self GET can return no assignment and revision zero without creating a row. An administrator creates an assignment explicitly using the authorized opaque profile picker, then uses revisions for later position/unit changes. Keep personal preferences and tenant directory data separate.

Corporate identity providers, group discovery/mappings, personal-token administration and MCP OAuth client registration require the appropriate ordinary verified identity. A PAT with a management-looking scope cannot bypass an identity-only gate. Read capability/readiness responses before selecting provider operations; do not assume every IdP exposes the same directory or photo data. Keep credentials server-side and handle returned one-time client/token secrets privately and once.

For application registrations, distinguish registering a client from the current user's consent and from an application successfully connecting. Authorized-application revocation affects the current user's grant; rotating an OAuth client secret is a separate administrator action. See [application registration](register-applications.md), [API permissions](api-permissions.md) and [people and organization](people-and-organization.md) for their exact boundaries.

## Finish with a response and recovery decision

Inspect the typed response for the new canonical identity, current revision and observed state. Keep safe request-reference metadata for support. On `401`, repair the host's identity flow; on `403`, discard denied private data and recheck current authority. On a revision conflict, display the newer state before asking again. On a timeout or disconnected write, reconcile the original operation and saved state before any further mutation.

Audit reads require `audit:read`; they are a view of authorized recorded activity, not a source of new authority. Keep private payloads, provider credentials and one-time secrets out of logs. Bound downloads to a caller-controlled new path or storage object, treat returned filenames as metadata, and clear cached binaries when the authorized context ends. Async cancellation controls the owned HTTP operation; durable jobs, runs and exports retain their own lifetimes.
