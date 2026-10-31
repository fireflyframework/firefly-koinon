<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Connect an external ECM

Use this guide when knowledge originates in an enterprise content management system. It identifies the supported ingestion boundary, the external integration's responsibilities and the records needed to preserve versions and permissions. For deployment-owned buckets, containers and volumes, use [storage configuration](storage-configuration.md).

## Current ECM connector inventory

| Surface in the current product | What it supplies |
| --- | --- |
| Canonical file upload and document/dataset content APIs | Authorized byte ingestion, source identities, historical versions/snapshots and guarded replacement. |
| Local, S3, Azure Blob and GCS stores | Deployment-owned persistence for bytes; these are not enterprise document-management connectors. |
| Entra/Google Workspace corporate adapters | Identity/group and supported personal-presentation workflows; not SharePoint/Drive file crawling. |
| Connected MCP applications and external review APIs | Explicit external read receipts and bounded reviewed text/file handoff, under the existing client/consent boundary. |

The shipped koinon backend/native document/structured route, configuration and dependency inventory contains no dedicated SharePoint, Google Drive, OneDrive, CMIS or WebDAV content connector. There is no implied ECM crawler, delta-token synchronization worker, checkout/check-in API, records-management policy engine or automatic external-ACL mirror. Installing a cloud object-store extra does not add those features.

## Integrate an external ECM through supported boundaries

An external integration owns ECM authentication, retrieval and its source-side permission decision. It then uses the [Python](../guides/python-knowledge.md), [TypeScript](../guides/typescript-knowledge.md) or [Java](../guides/java-knowledge.md) SDK with a narrowly scoped koinon identity and an explicitly authorized destination. For a file handoff, use the actual upload/content APIs and retain their receipts before processing another item.

Keep an integration ledger containing the real ECM system/object/version identifiers, retrieval time, original-byte digest, permission decision, selected destination and returned koinon source/asset/version identities. Preserve externally reported metadata as such. A display URL, catalog metadata value or caller-supplied “version” does not create a trusted immutable `SourceReference`. Do not modify blob keys or manufacture history rows to simulate imported provenance.

For supported MCP handoff, use genuine server-issued read receipt IDs and the typed external text/file review flow. Origin remains explicitly external/unverified where recorded. The embedded person-review component supplies the actual approval authority; public SDK callers cannot fetch a component-only approval nonce or automatically consent on the user's behalf. See [MCP knowledge management](../guides/mcp-knowledge-management.md).

External permissions are not automatically copied into koinon. Choose a destination whose actual memberships and publication policy admit the content, and explicitly manage later access changes through existing authorized operations. A service account's ECM read permission is not permission to publish the file to every member of a shared workspace. Position/department metadata is not an access grant.

Remote edits/deletions and permission revocations need an explicitly governed integration policy. Reconcile the real external version with the current returned koinon revision/digest before replacement; never bypass `If-Match`, infer an overwrite or replay an unknown upload outcome. Capture enough information to explain a stale or removed source without claiming live synchronization. The API does not automatically revoke koinon grants when an ECM ACL changes.

## Keep bulk and recovery boundaries explicit

Canonical upload is one file per request, with a configured default limit of 32 MiB. It is not a durable atomic bulk import. Bound a caller-owned queue, process one admitted item at a time, persist each accepted receipt and stop on ambiguous outcomes. Existing dataset append and selected lifecycle operations have explicit idempotency keys; a plain source upload does not acquire idempotency merely because the integration has an external object ID.

The retained structured package's bulk handlers and multipart byte transport do not establish canonical batch authorization, distributed backpressure, restart recovery or an unlimited upload contract. ECM chunk transfer, cloud multipart sessions and server knowledge ingestion are different layers. Qualify throughput, partial failures, cancellation and replay policy separately using owned test data and real deployment identities before claiming production synchronization or large-scale ingestion.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
