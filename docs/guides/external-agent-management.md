<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Manage authorized knowledge from an external agent

An external agent connects **to koinon** through the installation's remote MCP endpoint. koinon remains responsible for the authenticated user, current role, credential scopes, selected space and every resource permission. Installing a plugin or giving a tool to a model does not grant access.

For hosted agents, start with the deployment's exact HTTPS `/mcp` URL and a pre-registered OAuth client. Each person signs in with their own account and reviews their space and requested permissions. The [Claude](connect-claude.md), [ChatGPT](connect-chatgpt.md) and [Grok](connect-grok.md) setup notes separate documented host features from completed client acceptance. The [PAT desktop extension](../integrations/desktop.md) is an alternative for hosts that support it.

## Connect the account before choosing tools

Choose one connection method. A remote connector uses the deployment URL and a registered OAuth client; every person completes their own sign-in and space consent. The desktop MCPB instead starts a local bridge with a separately issued personal access token. A skills archive contains instructions only. Neither installing an archive nor importing a GitHub marketplace configures an account or grants a role.

Start by asking the agent to call `koinon_context` and show the actual organization and space it can access. Compare these with the intended task before retrieving or changing anything. If the client cannot accept koinon's pre-registered-client OAuth setup, stop at connection setup. Do not select unauthenticated access, invent a callback or paste a token into a client-secret field.

| Intended operation | Required credential scopes | Other boundary |
| --- | --- | --- |
| Browse, fetch, inspect schema/provenance or availability | `catalog:read` | Current access to every returned resource |
| Search document evidence | `catalog:read`, `knowledge:search` | Current source permissions |
| Query a dataset | `catalog:read`, `query:execute` | Governed read-only query and current dataset bounds |
| Inspect your existing answer audit | `catalog:read`, `chat:use` | Your own existing koinon run, not the external chat |
| Read your authorized activity summary | `catalog:read`, `activity:read` | Current credential/workspace coverage; missing observations stay unknown |
| Organize ordinary catalog entries | `catalog:read`, `catalog:write` | Current role, exact source/destination and stale-state checks |
| Stage and approve generated content or file ingestion | `catalog:read`, `catalog:write`, `ingest:write` | Supporting evidence access plus explicit human review in a compatible MCP Apps host |
| Inspect platform health/system information | `catalog:read`, `audit:read` | Current unbounded organization administrator PAT only; hidden from workspace OAuth |

The client registration's permitted scopes are a ceiling, not a role assignment. The user must approve the scopes, and canonical resource policy must independently allow the operation. `audit:read` is not OAuth-requestable; do not expand a workspace connection to obtain organization-wide health. Read [MCP authentication](../operations/mcp-authentication.md) for the exact OAuth/PAT distinction.

## Choose the operation

| Task | Tools | What the user must decide |
| --- | --- | --- |
| Browse and retrieve evidence | `koinon_context`, `koinon_list`, search, fetch, schema, query and provenance tools | Which authorized sources and question to use |
| Check current asset availability | `koinon_availability` | Exact asset IDs, with an optional matching space |
| Create an organizational folder | `koinon_create_folder` | Exact kind, parent and name; this does not create knowledge content |
| Rename, describe or tag ordinary catalog entries | `koinon_update_catalog` | Exact fields against the fetched timestamp; metadata replaces public metadata |
| Move a collection or corpus | `koinon_move_folder` | Exact current parent, timestamp and compatible destination inside the same project |
| Recoverably archive or restore | `koinon_archive_catalog`, `koinon_restore_catalog` | Exact entry and current timestamp; neither permanently deletes data |
| Publish or update AI-derived content; import selected file bytes | Existing stage/prepare and embedded-review tools | Exact content, evidence, destination and explicit human approval in a compatible MCP Apps host |

Ordinary organizational tools require `catalog:read` and `catalog:write`; availability requires `catalog:read`. A scope-only denial may request a supported OAuth scope upgrade. A denied role, foreign space or asset restriction cannot be fixed by requesting wider scopes. The server checks current authority again when the operation runs, including after account revocation or a role change.

The list tool supports bounded paging and filters for space, project, parent, kind, name query, status, format, tag, archived entries and sort order. Fetch the exact current entry before changing it; do not infer an ID, timestamp or parent from a display name.

## Walk through a catalog change

Suppose the user asks: “Create a collection named Renewal research under this project, then tag it for the operations team.” This requests an organizational folder and public metadata, not a generated knowledge publication.

1. Call `koinon_context`. Use `koinon_list` to locate the authorized project and inspect its returned id, kind and space. A matching name alone is insufficient when several entries share it. Page or narrow the listing until the intended parent is established.
2. Call `koinon_create_folder` once with `kind="collection"`, that project id as `parent_id`, the exact user-requested name and the current tenant id. Creating a workspace/project may require a different role than creating a collection; let the canonical response decide.
3. Retain the returned collection id and its `updated_at`. If the response is lost, follow the unknown-result section below instead of issuing another create.
4. Before changing an existing entry, re-list its current authorized parent and match the exact id. The MCP catalog has no dedicated get-folder-by-id tool. The canonical API and SDK do expose an exact catalog read; a client restricted to MCP must use the available bounded listing rather than fabricate a fetch mode.
5. Read the current public metadata and prepare the complete intended result. For a tag update, preserve fields the user intends to keep. Call `koinon_update_catalog` with the exact latest timestamp and resulting metadata map.

For example, the update tool accepts this shape. These identifiers and timestamp are illustrative; use values actually returned by your deployment:

```json
{
  "tenant_id": "tenant_example",
  "entry_id": "collection_example",
  "expected_updated_at": "2026-11-01T15:30:00Z",
  "changes": {
    "metadata": {
      "tags": ["operations", "renewals"]
    }
  }
}
```

That example replaces the public metadata map. It must not be copied over an entry containing other fields the user wants to retain. A successful response supplies the new timestamp for a later action. If the tool reports `CATALOG_CHANGED`, show the newly observed state and obtain the intended change against it; silently refreshing the timestamp defeats the concurrency protection.

Move a collection or corpus only after inspecting both its existing parent and the compatible destination in the same project. Use the live `koinon_move_folder` schema for its exact previous-parent and timestamp fields. For archive or restore, use the returned entry id and latest timestamp; include archived entries when locating a restore target. Neither action permanently deletes the file bytes or publishes a new curated version.

The same canonical operations are available to direct integrations in the [catalog API reference](../reference/api/catalog.md) and the typed [SDK reference](../reference/sdk-api.md). A direct API/SDK call is not a workaround for a denied MCP operation or a missing human content approval.

## Keep concurrent changes visible

Patch, archive and restore accept an optional exact `expected_updated_at` precondition in the canonical API. Patch carries it in its JSON body; archive and restore use the query parameter of that name. Legacy callers that omit it retain their existing behavior. The new MCP tools require it. Native services compare the timezone-aware timestamp under the existing tenant and row locks. A stale value returns `CATALOG_CHANGED` without applying that change.

Folder moves retain their existing exact previous-parent and timestamp checks. Protected system roots, incompatible destinations, cross-space/project moves, cycles and busy descendants remain rejected by the canonical service.

Metadata is a complete replacement of the public metadata map, not a merge patch. Read the entry, preserve the fields the user intends to keep, then include the exact resulting map. Tags use `metadata.tags`. Internal source and intake fields are excluded from public metadata and remain server-protected. These tools cannot publish a curated knowledge item by changing a catalog field.

## Resolve unknown results before another decision

Folder creation is a single attempt and has no idempotency receipt. A lost response can occur after the folder committed. The tool reports an unknown outcome and tells the caller not to repeat the create request. Inspect the authorized parent and recorded activity before deciding whether anything remains to be done. The adapter does not automatically replay it.

Do not refresh a stale precondition merely to force a change. Show the newly observed state to the user and obtain their intended change against it. Archive is recoverable; permanent deletion, membership/grant changes, provider credentials and security administration are not exposed by these tools.

## Respect the content-review boundary

Organization of existing entries is separate from publishing generated knowledge. The existing AI-content and file workflow still requires negotiated MCP Apps, its private metadata boundary and an explicit human decision. A model's confirmation text or an OAuth consent is not that decision. A client without the required review capability can use supported reads and user-requested catalog organization, but cannot complete those content/file publication operations. There is no automatic per-write browser redirect or silent direct-publication fallback.

Processing history remains available through its native API/SDK to callers with `jobs:manage`; this tranche does not expose a broader processing tool or add that scope to workspace OAuth. The tool catalog is intentionally narrower than the complete [API and SDK reference](../reference/sdk-api.md). Hosted tool toggles, visual review support and real account-linking still require testing in the actual client.

## Verify the connection you intend to use

Before describing a client integration as accepted, use a controlled authorized space to check context, one supported read, an allowed organizational change and a denied change outside that space. If content publication is required, verify the actual embedded review, cancel once and then approve an exact new proposal. Inspect the resulting operation and source references. A local component fixture or marketplace validator does not establish that the real host preserves private metadata.

Revoke the connection in koinon's **Authorized applications**, or revoke its separate PAT in **API tokens**, then confirm that the next governed operation is denied. Removing the host plugin alone does not revoke the server credential. Reconnect after expiry because the current OAuth implementation does not issue refresh tokens. Never repeat an uncertain write merely to test reconnect behavior.
