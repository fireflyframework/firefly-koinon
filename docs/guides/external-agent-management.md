<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Manage authorized knowledge from an external agent

An external agent connects **to koinon** through the installation's remote MCP endpoint. koinon remains responsible for the authenticated user, current role, credential scopes, selected space and every resource permission. Installing a plugin or giving a tool to a model does not grant access.

For hosted agents, start with the deployment's exact HTTPS `/mcp` URL and a pre-registered OAuth client. Each person signs in with their own account and reviews their space and requested permissions. The [Claude](connect-claude.md), [ChatGPT](connect-chatgpt.md) and [Grok](connect-grok.md) setup notes separate documented host features from completed client acceptance. The [PAT desktop extension](../integrations/desktop.md) is an alternative for hosts that support it.

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
