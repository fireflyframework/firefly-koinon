<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Python: administration and safe client operations

Use the [Python quickstart](headless-python.md) with an organization-scoped credential for organization management. A token's scopes intersect with its owner's current roles and resource bounds. Issuing a management scope does not turn a workspace administrator into an organization administrator. See the [role and permission tables](api-permissions.md).

## Work from observations to deliberate changes

Start by reading current context and selecting the organization you administer. Distinguish organization authority from workspace administration: a workspace role cannot be widened by requesting an organization-management scope. For each task, use the [permission matrix](api-permissions.md) to choose an ordinary identity or a permitted bounded API credential before constructing an input.

[Download the complete administration source](../examples/python/README.md). Its default entry point reads only the current account's position in the selected organization, using the self/profile boundary. Provider, member, agent, knowledge-settings and index helpers are separate operations; importing the file or constructing a client does not execute them.

For a production host, build an administrative screen or command in two stages: load and display the current state, then submit the reviewed typed change after a person chooses it. Retain the reviewed revision, operation identity and safe response metadata. Do not turn a permission failure into a request for every available scope or retry an unknown write automatically.

## Run the read-only chapter

Download `support.py` and the selected chapter file into the same directory, then use the Python environment from setup. [Complete source and build instructions](../examples/python/README.md) include [the entry-point file](../examples/python/administration.py). Use the organization already selected in `KOINON_TENANT_ID`. Keep credentials in the approved environment rather than adding them to these commands.

```sh
python administration.py
```

The result prints the current tenant position ID, job title and available revision. A missing assignment can have null ID and revision zero; the GET does not create it. If authorization fails, return to the setup chapter and inspect current context/scopes instead of broadening the request. The remaining helpers define the intended mutations, but this command does not invoke them.

## Select the right management group

| Task | Python helpers | Boundary |
| --- | --- | --- |
| Providers and agents | `configuration`, `create_provider`, `update_provider`, `validate_provider`, `agents`, `create_agent`, `update_agent`, `validate_agent` | `providers:write`/`agents:write`; discovery, validation and a successful model/tool run are separate observations. |
| Source connections and knowledge roles | `knowledge_connections`, `create_knowledge_connection`, `update_knowledge_connection`, `knowledge_roles` | `sources:configure`; use current revisions and explicit tenant/workspace role assignments. |
| Embedding/index lifecycle | `plan_knowledge_index`, `create_knowledge_index`, `knowledge_index`, `activate_knowledge_index`, `cancel_knowledge_index`, `resume_knowledge_index` | `indexes:manage`; plan first, preserve idempotency keys, activation preconditions and observed job state. |
| Durable jobs | `jobs`, `job`, `cancel_job` | `jobs:manage` plus current resource authority; a list may be items-only. |
| Access and activity | `members`, `update_member`, `invitations`, `audit` | Organization/workspace authority and `members:write` or `audit:read`, as appropriate. |
| Personal account | `profile`, `update_profile`, `set_avatar`, `avatar_download`, `delete_avatar` | The authenticated account only; preferences and photos are global, positions are tenant-bound. |
| Organization settings | `organization_chat_settings`, `update_organization_chat_settings`, branding/knowledge settings helpers | Each setting has its own permission and revision; reading the saved default does not configure a model. |

The SDK transports explicit requests; it does not install embeddings, start workers, provision credentials or configure the deployment. Native provider/connection ownership and availability are server observations. Use the [knowledge runtime guide](../concepts/knowledge-runtime.md) and the deployment's configuration guidance before enabling a workflow.

Personal token creation/revocation, corporate identity provider administration, directory group discovery, group-to-role mappings, corporate profile mappings and OAuth client registration have ordinary verified-identity gates. A PAT or application credential cannot bypass them by adding `identity:manage`. Keep IdP credentials on the server and never include them in chat or logs. MCP resource tokens are separate from API bearer credentials.

## Configure a provider and an agent in order

Read the current provider observations through configuration before creating another provider. Select a supported provider kind and API variant, the deployment-approved endpoint, and actual model IDs. Supply real credentials through your approved secret source only when the provider requires them. The typed `ProviderInput` in the complete source accepts the reviewed configuration; it does not contain a sample provider key, discover secret values, or prove connectivity. Never print the input or a one-time secret return.

Call `create_provider` only after that configuration is reviewed. Save the returned provider ID and inspect its observed availability. A separate validate operation can contact the configured external system and must be run intentionally. Successful configuration serialization is different from a successful provider test, and both are different from a completed answer.

Next build a typed agent input using that actual provider ID, a model ID available there, a chosen knowledge scope and only the tools needed for the task. The complete source's agent helper keeps these inputs explicit. Call `create_agent` with `agents:write`, retain its ID, and inspect its validation/availability. Selecting tools or an agent does not grant the agent more knowledge access than the current caller.

Finally read the organization's chat settings, display the selected default agent and revision, and update that default only after a person confirms it. Omitting a patch field preserves it; explicit null clears a field only where the endpoint permits it. Preserve unrelated settings. Re-read after a revision conflict instead of taking a new revision and silently replaying the old decision.

The complete functions below construct a bounded reader agent from real provider/model IDs and update only the reviewed document policy. They do not validate a provider or start a run. Call them from separate confirmed host actions, then inspect the returned IDs, revisions and observed availability.

```python
from typing import Literal
from koinon_sdk import (
    KoinonClient, AgentConfiguration, AgentInput, KnowledgeScope,
    OrganizationKnowledgeSettings, OrganizationKnowledgeSettingsInput,
)

async def create_reviewed_agent(
    client: KoinonClient,
    tenant: str,
    provider_id: str,
    model_id: str,
    scope: KnowledgeScope,
    person_confirmed: bool,
) -> AgentConfiguration:
    if not person_confirmed:
        raise ValueError("Review the configured model, tools and scope first")
    return await client.create_agent(
        tenant,
        AgentInput(
            name="Knowledge reader",
            provider_id=provider_id,
            model_id=model_id,
            scope=scope,
            tools=["search_knowledge", "inspect_schema", "query_dataset"],
            enabled=True,
        ),
    )

async def set_reviewed_document_mode(
    client: KoinonClient,
    tenant: str,
    reviewed: OrganizationKnowledgeSettings,
    mode: Literal["rag", "rlm"],
    person_confirmed: bool,
) -> OrganizationKnowledgeSettings:
    if not person_confirmed:
        raise ValueError("Review the selected mode and retained settings first")
    documents = reviewed.documents.model_copy(update={"answer_mode": mode})
    return await client.update_organization_knowledge_settings(
        tenant,
        OrganizationKnowledgeSettingsInput(
            expected_revision=reviewed.revision,
            documents=documents,
            structured=reviewed.structured,
        ),
    )
```

## Choose RAG or RLM and plan index work

Read `organization_knowledge_settings` before changing document behavior. Copy its document and structured sections into the typed settings input, change only the chosen supported value, and send the reviewed revision. The complete source demonstrates changing document `answer_mode` while preserving all other document parameters and the structured settings. Use `settings:write` and current organization authority.

RAG retrieves an admitted evidence subset for an answer. RLM uses the configured bounded native exploration policy. Neither setting provisions a provider, changes a source connection, imports an embedding model, or proves a successful run. Inspect the [knowledge runtime prerequisites](../concepts/knowledge-runtime.md) before enabling either mode, and use the answer audit to distinguish recorded retrieval and RLM actions from missing historical metadata.

For an embedding rebuild, read available choices and call `plan_knowledge_index` with the intended workspace/domain and actual provider/model IDs. Display the plan's scope and effects first. Creating with `create_knowledge_index` is a separate action requiring `indexes:manage` and a stable caller-owned idempotency key. Retain the returned index/job identity and inspect `job` or the index state before assuming processing finished.

Activation is another explicit transition. Use the current revision and expected active index/connection preconditions from the reviewed state. Canceling HTTP does not cancel a server rebuild. Use its explicit cancellation operation when requested; resume requires its own current preconditions and stable request identity. A failed or pending state is not permission to discard history or invent a recovery action.

## Plan embedding work explicitly

Select an admitted embedding provider/model and the intended workspace. This helper requests the server's plan/validation; it does not create or activate an index:

```python
from koinon_sdk import KoinonClient, IndexPlanInput, IndexPlanView

async def plan_embeddings(
    client: KoinonClient, tenant: str, workspace: str, provider_id: str, model_id: str,
) -> IndexPlanView:
    return await client.plan_knowledge_index(tenant, IndexPlanInput(
        workspace_id=workspace, domain="documents", provider_id=provider_id, model_id=model_id,
    ))
```

Review the plan before an explicit `create_knowledge_index` call. Creation/resume needs a stable idempotency key; activation is separate and carries current revision, active-index and connection-revision preconditions. Inspect durable job outcomes before switching serving state. Supported configuration and a typed plan do not establish successful embedding/provider execution. Use the [runtime guide](../concepts/knowledge-runtime.md) for the distinction between lexical retrieval, embedding indexes and the active serving configuration.

## Preserve omitted fields, explicit null and revisions

Pydantic input models keep `model_fields_set`; SDK writes serialize with `exclude_unset=True`. An omitted field preserves the saved value. Explicit `None` clears a field only where the endpoint permits clearing it. False and zero are values, not omissions. For example:

```python
from koinon_sdk import (
    KoinonClient, OrganizationPersonPatch, OrganizationPerson,
    OrganizationChatSettingsInput, OrganizationChatSettings,
)

async def clear_manager(
    client: KoinonClient, tenant: str, person_id: str,
) -> OrganizationPerson:
    current = await client.organization_person(tenant, person_id)
    return await client.update_organization_person(
        tenant, person_id,
        OrganizationPersonPatch(expected_revision=current.revision, manager_id=None),
    )

async def clear_default_agent(client: KoinonClient, tenant: str) -> OrganizationChatSettings:
    current = await client.organization_chat_settings(tenant)
    return await client.update_organization_chat_settings(
        tenant, OrganizationChatSettingsInput(
            expected_revision=current.revision, default_agent_id=None,
        ),
    )
```

These are explicit writes. Clearing the chat default requires organization-level `agents:write`; editing a position requires organization-level `members:write`. Releasing provider ownership uses `manage_locally=True`, not a null provider ID. Reattaching requires `managed_provider_id`, both member and identity management permissions, and an active enabled source mapping. Existing values remain until a verified sign-in supplies a new observation. Position changes never grant a role.

`organization_person_self` reads the current account's tenant position. `organization_people`, `organization_units` and `organization_person_reports` use bounded server pages and the chosen visibility scope. Shared-workspace viewing requires `workspace_id`; asset-restricted tokens cannot browse this directory. Directory avatars use `organization_person_avatar`, with the returned assignment or visible profile ID. Keep private URLs/bytes scoped to the current user, tenant and permissions, and discard cached rows and photos after identity, permission or server-denial changes. The [people guide](people-and-organization.md) describes source ownership and all 15 operations.

## Handle failure without repeating an unknown write

```python
from koinon_sdk import ApiError, KoinonClient, CatalogEntry

async def read_entry(client: KoinonClient, tenant: str, entry_id: str) -> CatalogEntry:
    try:
        return await client.get(tenant, entry_id)
    except ApiError as error:
        # Correlate with operators without logging bearer tokens or request bodies.
        print(error.status, error.code, error.transaction_id)
        raise
```

| Outcome | Caller action |
| --- | --- |
| `401` | Renew through the host identity flow or require sign-in; invalidate private cached state. |
| `403` | Stop using the denied view and discard its cache; recheck current roles, token scope and resource bounds. |
| `409` / content-precondition conflict | Reload the current revision/digest, show the change and ask for a new decision. |
| Validation failure | Correct the typed request; do not coerce roles, revisions or unknown fields to make it pass. |
| Timeout, disconnect, `pending` or unresolved commit | Retain request/idempotency identity and reconcile; a missing response is not proof of rollback. |

Use `offset_pages` only for actual numbered `Page` endpoints, and `cursor_pages` only where the endpoint returns a cursor. Organization/history pages have their own typed envelopes; inspect their `page`/`pages`/`has_next` metadata explicitly. Page helpers stop on inconsistent paging rather than fetching everything or inventing pages. `asyncio` task cancellation interrupts the active HTTP operation; close the client and any partially consumed stream/generator. A durable job/run needs its own explicit cancellation request.

Binary helpers return bytes or `BinaryDownload` metadata; the client does not choose a local output path. Treat returned filenames as untrusted display metadata, bound any persistence yourself, and never turn private originals or avatars into public links. See the [generated reference](../reference/sdk-api.md) for exact methods and [application registration](register-applications.md) for identity-only administration.

## Manage access separately from presentation

List members in the authorized organization/workspace and select the exact membership to change. A typed member update changes `role` or `active`; it is an access decision requiring `members:write` and current membership-management authority. Review the affected person, scope and change before sending it. A title, department, unit, reporting line or avatar is presentation data and never grants a role.

Use `organization_person_self` for the current tenant position and `profile` for the personal account. The directory has its own visibility setting and current membership guard; a shared-workspace projection does not expose the entire organization. A self GET can return no assignment and revision zero without creating a row. An administrator creates an assignment explicitly using the authorized opaque profile picker, then uses revisions for later position/unit changes. Keep personal preferences and tenant directory data separate.

Corporate identity providers, group discovery/mappings, personal-token administration and MCP OAuth client registration require the appropriate ordinary verified identity. A PAT with a management-looking scope cannot bypass an identity-only gate. Read capability/readiness responses before selecting provider operations; do not assume every IdP exposes the same directory or photo data. Keep credentials server-side and handle returned one-time client/token secrets privately and once.

For application registrations, distinguish registering a client from the current user's consent and from an application successfully connecting. Authorized-application revocation affects the current user's grant; rotating an OAuth client secret is a separate administrator action. See [application registration](register-applications.md), [API permissions](api-permissions.md) and [people and organization](people-and-organization.md) for their exact boundaries.

## Finish with a response and recovery decision

Inspect the typed response for the new canonical identity, current revision and observed state. Keep safe request-reference metadata for support. On `401`, repair the host's identity flow; on `403`, discard denied private data and recheck current authority. On a revision conflict, display the newer state before asking again. On a timeout or disconnected write, reconcile the original operation and saved state before any further mutation.

Audit reads require `audit:read`; they are a view of authorized recorded activity, not a source of new authority. Keep private payloads, provider credentials and one-time secrets out of logs. Bound downloads to a caller-controlled new path or storage object, treat returned filenames as metadata, and clear cached binaries when the authorized context ends. Async cancellation controls the owned HTTP operation; durable jobs, runs and exports retain their own lifetimes.
