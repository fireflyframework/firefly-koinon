<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Python: administration and safe client operations

Use the [Python quickstart](headless-python.md) with an organization-scoped credential for organization management. A token's scopes intersect with its owner's current roles and resource bounds. Issuing a management scope does not turn a workspace administrator into an organization administrator. See the [role and permission tables](api-permissions.md).

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
