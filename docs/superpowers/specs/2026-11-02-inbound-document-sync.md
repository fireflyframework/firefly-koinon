<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Inbound document synchronization and file journeys

Status: implementation design, not a statement of released connector support. The current product has durable file intake and source replacement, but no SharePoint, OneDrive or Google Drive synchronization connector. Keep the published ECM inventory accurate until each connector has passed its release gates.

## Product boundaries

People connect their own Microsoft or Google account, choose a source folder and map it to an authorized Library project or folder. They review the initial import and enable a continuing inbound synchronization. The source remains authoritative for synchronized originals. koinon never writes, renames, moves, shares or deletes files in the remote provider.

Library projects, source permissions and credential scopes all constrain access. A source connection is not an AI model provider, an identity-directory synchronization or an MCP authorized application. Keep those concepts and settings separate. Chat, REST, SDK and MCP use the same imported catalog identities, versions and permission decisions as Library.

Selecting a mapping authorizes the stated recurring import and replacement policy. It does not authorize publication of new AI-derived conclusions, which still requires the existing explicit human review. Changing a destination, expanding a source root or changing the removal policy requires a new review.

## Uploader and viewer behavior

Fetch effective capabilities before selection: supported formats by document/dataset mode, available converters, maximum file bytes, maximum batch bytes, file count and destination requirements. The browser's accept hint and early feedback use these descriptors; the server still checks actual bytes, archive expansion limits, parser availability and current permissions. A file extension is not sufficient admission evidence.

Show every selected item immediately, including its name, formatted size and destination. Invalid files remain visible with a specific reason and a Remove action. Mixed selections never silently lose rejected items. Show selected count and total bytes against the effective limits, with file-level errors and a clear action for submitting valid items.

Keep transfer and knowledge processing distinct. Use queued, uploading, uploaded, waiting for processing, processing, ready to search, failed, cancelled and expired states where the underlying receipt supports them. Show byte progress only when measured; processing stages use indeterminate progress or a genuine stage count. An uncertain outcome is a reconciliation state, not a retryable failure. Partial batch completion remains visible, with successful items preserved and safe actions scoped to the failed or pending items.

Upload, cancel and resume controls retain canonical idempotency and lease rules. Bounded transfer concurrency and ingestion worker capacity are installation settings; selecting 50 files must not launch 50 parsers. Do not load whole batches into browser or worker memory. Originals use the configured private object storage; local temporary files have bounded size, lifetime and cleanup ownership.

Document details and previews show the original name/format/size, uploader or source account, source location, source modification time, import time, processing status, current version and last successful synchronization. Preview, download, extracted content and dataset views each retain their real capability and permission checks. A conversion failure never masquerades as a successful preview. Present an authorized download or an actionable unsupported-preview state.

## Connections and mappings journey

1. In Library, choose Import from a connected source. Administrators enable providers and configure application credentials in Sources and synchronization; users manage their own connected accounts.
2. Choose SharePoint, OneDrive or Google Drive. Sign in with delegated read access and see the connected account and provider tenant. Do not reuse an identity-login token as a file API token or match accounts merely by email.
3. Browse only source sites, libraries, drives and folders the connected account can read. Show a breadcrumb, search and pagination. Store stable provider IDs, not display paths. Do not follow shortcuts or shared links outside the chosen root implicitly.
4. Choose an existing authorized Library project/folder, or create the required space, project and folder through their canonical policies. New installations have an empty Library: do not create predefined or protected system destinations, including in company-specific deployments. If the user cannot create a destination, explain how to request access rather than importing elsewhere. Display actual destination access and explain that source access is also required for synchronized content.
5. Review a paginated import preview: supported/skipped files, known bytes, unknown-size files, conflicts, proposed folders and estimated work. Unknown totals remain unknown. Configure recursion, format selection, schedule and removal handling. Existing mapping overlaps are reported before starting.
6. Start the initial import. A persistent run page shows enumeration, downloaded bytes, queued/processing/ready items, failures and remaining work. Closing the page does not cancel the job.
7. After the initial import, show last checked, last successful synchronization, next scheduled run and source authorization health. Offer Sync now, Pause, Resume, Review mapping changes and Disconnect according to current permissions.

Library labels synchronized files with their provider and origin, without adding a dense technical card to every row. A details drawer shows the run, versions and provenance. The administrator's Operations view supplies full worker attempts, leases, provider throttling, errors and reconciliation actions. User activity shows only the user's authorized items and operations.

## Permissions and personal connections

Use delegated OAuth authorization code flows with PKCE where supported, exact configured callbacks, validated issuer/tenant and encrypted refresh credentials. Request only read scopes needed by the selected provider capability. Offline background access is explicit in consent. A revoked or expired grant pauses dependent work and produces Reconnect required; it never falls back to an installation-wide service credential.

For synchronized knowledge, effective read authority is the intersection of current koinon project/resource access and current source access for the requesting person. The importer's source token must never authorize another reader. Each reader links the appropriate provider account when necessary. A koinon administrator may manage a mapping but does not automatically gain permission to read remote content.

The source-access policy needs a server-owned link from each imported version to the provider object and connected-account context. Authorize candidate source identities before fetching text for a model, rendering excerpts, previews, exports, audits or remembered context. Revalidate at the existing output/commit fences. Use provider batching where available; do not hold a primary database transaction or connection during network checks. Failed or indeterminate permission checks do not release protected content. Any future cache must have a documented freshness bound and cannot promise instantaneous external revocation.

Permission checks must respect provider download/export restrictions as well as item visibility. Do not reconstruct effective permissions from an incomplete list of remote ACL entries. Directory groups, display names and file ownership are metadata, not grants. This source policy composes with the project authority work; synchronization cannot be enabled before all consumers enforce it.

## Provider contracts

Microsoft Graph supplies drive delta pages, continuation links and a final delta cursor. Follow the bounded continuation chain and preserve the cursor only after the corresponding observations and durable work have been recorded. Interpret deletion markers separately from access errors. Use stable drive/item IDs for folder ancestry and rename handling. These behaviors follow the [Graph delta contract](https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0).

When a delta cursor expires or the provider requests a full resynchronization, pause incremental consumption and start a bounded enumeration generation. Retain local exclusions, previous origin bindings and immutable receipts. Do not interpret absence from an incomplete scan as a deletion. Reconcile removals only after a complete authorized enumeration and the reviewed removal policy; never follow a recovery path that uploads differences to the source.

For Microsoft downloads, handle the provider's preauthenticated download redirect explicitly. Do not forward the Graph bearer credential to the content host, log signed URLs, or accept arbitrary network destinations. Stream through the governed storage path and verify size/hash before admission. See [Graph content download](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0).

Google Drive uses the change feed with a start token and paginated continuation. Capture a token before the initial enumeration, then consume subsequent changes to reconcile changes during the scan. Keep checkpoints separate by connected account and drive. See [Drive change retrieval](https://developers.google.com/workspace/drive/api/guides/manage-changes). Shared drives require explicit shared-drive request support and correctly scoped drive queries, as described in [shared drive support](https://developers.google.com/workspace/drive/api/guides/enable-shareddrives).

For Google folder synchronization, select a genuinely read-only scope capable of enumerating the authorized root. `drive.file` permits writes to selected files and is not a substitute for a recursive read-only folder contract. `drive.readonly` has provider verification requirements that operators must understand. See [Google's scope definitions](https://developers.google.com/workspace/drive/api/guides/api-specific-auth). Native Google documents require explicit supported export conversions, with provider limits and original object/version provenance; never invent a file size or claim every native document is downloadable.

Start with polling through durable scheduled jobs. Provider notifications may later wake the same reconciliation worker, but are hints rather than an alternate import path. Renewal failures, duplicate events and missed notifications must not lose changes. Respect provider retry guidance, including Graph `Retry-After`, as described in [Graph throttling](https://learn.microsoft.com/en-us/graph/throttling). No file mutation endpoint belongs in a connector's transport allowlist.

## Durable processing and PyFly ownership

PyFly owns reusable typed provider ports, HTTP transport constraints, OAuth credential lifecycle, scheduling, bounded concurrency and transactional outbox behavior. koinon owns mapping review, project authority, source-version bindings, ingestion orchestration, user journeys and audit. Use native DI beans, repositories and configuration properties with DTOs, mappers, services and controllers in separate modules.

The existing PyFly `ContentSource` contract describes changed files and a local `Path`; it does not express deleted objects, permission loss, typed change pages or streaming into configured storage. Extend the framework with a compatible versioned change-page/streaming contract rather than manufacturing zero-byte files for deletions or putting an entire downloaded file in memory. Preserve existing source implementations and their cursor behavior. Do not call an optional SharePoint example a shipped adapter.

Store source connections, revisioned mappings, run records, change observations, per-item attempts and origin bindings in typed primary repositories. Keep secrets outside these DTOs and public snapshots. A change observation records provider/account/drive/object IDs, remote version, mapping revision, event kind and an immutable operation key. The origin binding records koinon source/asset/version IDs, downloaded hash and bytes, transformation details and commit receipt.

Workers follow short database units: reserve a bounded lease, perform remote I/O without holding a database connection, persist the observation and enqueue ingestion atomically through the outbox, then acknowledge the checkpoint. A persisted observation is not a claim that ingestion succeeded. The run reports discovery, transfer and indexing checkpoints independently. Job retries reuse the exact operation identity and native receipts; unknown publication outcomes enter reconciliation instead of creating a second source.

Assign each origin object a monotonic observation generation and use compare-and-swap at publication against its latest admitted observation, mapping revision and local retirement state. A slow older download or parser must not replace a newer published version or resurrect a deletion or exclusion. Provider feeds can repeat an object within a delta sequence; retain page order and reconcile its final observed state before completing that sequence. A mapping lease alone does not order different versions of one object.

Use per-provider, per-account, per-installation and worker limits. Lease heartbeats and fencing prevent a superseded worker from advancing a cursor or publishing a version. Restart tests must cover every boundary between byte storage, queue admission, native commit and acknowledgement. The scheduler must not create duplicate runs for an already active mapping. Pausing stops new admissions; safe in-flight work finishes or cancels under existing lease rules.

## Changes, removal and mapping revisions

| Event | koinon behavior |
| --- | --- |
| New supported remote file | Create one origin-bound source through durable intake |
| Content changed | Verify the current binding/revision and create a traced replacement version; keep the old version until the new commit is valid |
| Name or path changed within the root | Update authorized organizational metadata using stable object identity; avoid unnecessary re-indexing |
| File moved outside the mapped root | Retire that mapping's imported knowledge according to its reviewed policy |
| Explicit remote deletion | Remove the item from retrieval and record a source tombstone; preserve immutable lineage/history under retention policy |
| Permission loss or ambiguous absence | Block affected source use and pause/reconcile; do not label this as confirmed remote deletion |
| User removes synchronized knowledge in koinon | Retire it locally and record an exclusion so the next sync does not recreate it; never delete the remote file |
| User restores an exclusion | Preview and explicitly resume import under current source/project permissions |
| Local edits conflict with remote replacement | Report a conflict; do not silently overwrite user-maintained knowledge or erase provenance |
| Mapping destination/root changes | Create a reviewed mapping revision, stop old admissions and reject stale worker commits; do not silently copy all knowledge into another project's audience |
| Connection removed | Stop dependent admissions and clear credentials; offer a separately authorized local-content retirement choice, with no remote action |

Changing a mapping is not an ordinary cross-project folder move. Preview affected items, existing grants, exclusions and unfinished work. The first implementation can require a new mapping and explicit retirement of the previous destination when a safe transfer contract is unavailable. The UI must describe that operation honestly rather than silently broadening access.

Deletion in Library, API, SDK and MCP must call the same canonical retire/archive operation and invalidate subsequent retrieval, memory reuse and previews. Permanent purge remains a separate retention-aware administrator operation. Neither archive nor purge may erase the fact that a historical answer used a particular source/version; a retained audit can indicate that source content is no longer available without releasing it.

## API, MCP and delivery gates

Provide typed endpoints and all supported SDK methods for connection status, source browsing, mapping preview/create/update, run/status/history, pause/resume, synchronization request, exclusions and local retirement. MCP exposes the same operations with explicit narrow scopes and current user identity. An assistant cannot complete external OAuth, approve its own mapping changes, receive refresh credentials or gain source access from the mapping owner.

Qualification includes a completely empty installation, authorized destination creation and the no-permission path without automatic fallback folders. Exercise version2 completing before version1, duplicate object observations, deletion while an earlier parse is running, and expired-cursor recovery interrupted before enumeration completes. Qualification also covers mixed supported/unsupported files, unknown sizes, large originals, Google export limits, partial batches, overlapping roots, rename/move/delete, permission removal, token expiry, invalid continuation links, throttling, restart after every persisted checkpoint, duplicate events, stale mapping revisions, local exclusions and constant bounded query/concurrency behavior. Include two users with different source access, two Library projects, API/MCP equivalence and remembered-output revocation.

Before release, run genuine delegated provider journeys against owned test folders and inspect provider audit/network evidence that no remote files were mutated. A mock adapter or HTTP fixture validates contracts only. Publish step-by-step installation, user connection, mapping, initial import, operation, recovery and uninstallation guides with actual screenshots after those screens exist. Keep source tests, packaged artifacts, hosted CI and live provider acceptance separate.
