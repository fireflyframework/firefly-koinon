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

The internal candidate checker accepts at most100 already locally admitted object/version references per call and uses at most four concurrent checks per process, shared across callers of that service. This bounds one permission-check operation; it is not a corpus-size limit or a distributed installation-wide quota. It does not enumerate drives, folders or delta feeds. Microsoft checks each selected item's metadata and content-download response without consuming the body or following its signed redirect. Google checks the selected item's metadata and `canDownload` capability. These are current delegated calls using the requesting reader's connection; OAuth refresh can add a token request. Provider batch APIs are not implemented in this slice.

Every consumption and output fence must obtain fresh observations; no remote permission cache or reusable authorization ticket is provided. A batch with an unreadable, changed or indeterminate candidate returns no observations. A successful observation records the object version and check time but does not lock the provider's ACL: revocation can occur immediately afterward. The complete integration must therefore recheck remote permission and current local origin/mapping revisions before releasing an output, while never claiming instantaneous revocation or retracting bytes already delivered. RLM directory metadata, previews, evidence and remembered output require the same protection as file bytes. The checker remains internal until those integrations are complete.

Each read captures its delegated token together with the exact owner, connection, verified account, credential revision, effective scopes and installation configuration. Before metadata or observations are returned, current authority must still match that capture. A concurrent rotation, scope reduction or reconnection invalidates the read even when the provider account is unchanged; the caller may request a fresh read, and no write or OAuth exchange is replayed automatically. Browse continuations also bind this authority revision, so an invalidated cursor requires restarting that browse. Immutable origin bindings record source identity/version and content provenance, not a mutable credential revision; a new reader observation binds the currently authorized grant each time.

## Provider contracts

Microsoft Graph supplies drive delta pages, continuation links and a final delta cursor. Follow the bounded continuation chain and preserve the cursor only after the corresponding observations and durable work have been recorded. Interpret deletion markers separately from access errors. Use stable drive/item IDs for folder ancestry and rename handling. These behaviors follow the [Graph delta contract](https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0).

When a delta cursor expires or the provider requests a full resynchronization, pause incremental consumption and start a bounded enumeration generation. Retain local exclusions, previous origin bindings and immutable receipts. Do not interpret absence from an incomplete scan as a deletion. Reconcile removals only after a complete authorized enumeration and the reviewed removal policy; never follow a recovery path that uploads differences to the source.

For Microsoft downloads, handle the provider's preauthenticated download redirect explicitly. Do not forward the Graph bearer credential to the content host, log signed URLs, or accept arbitrary network destinations. Stream through the governed storage path and verify size/hash before admission. See [Graph content download](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0).

Google Drive uses the change feed with a start token and paginated continuation. Capture a token before the initial enumeration, then consume subsequent changes to reconcile changes during the scan. Keep checkpoints separate by connected account and drive. See [Drive change retrieval](https://developers.google.com/workspace/drive/api/guides/manage-changes). Shared drives require explicit shared-drive request support and correctly scoped drive queries, as described in [shared drive support](https://developers.google.com/workspace/drive/api/guides/enable-shareddrives).

For Google folder synchronization, select a genuinely read-only scope capable of enumerating the authorized root. `drive.file` permits writes to selected files and is not a substitute for a recursive read-only folder contract. `drive.readonly` has provider verification requirements that operators must understand. See [Google's scope definitions](https://developers.google.com/workspace/drive/api/guides/api-specific-auth). Native Google documents require explicit supported export conversions, with provider limits and original object/version provenance; never invent a file size or claim every native document is downloadable.

Start with polling through durable scheduled jobs. Provider notifications may later wake the same reconciliation worker, but are hints rather than an alternate import path. Renewal failures, duplicate events and missed notifications must not lose changes. Respect provider retry guidance, including Graph `Retry-After`, as described in [Graph throttling](https://learn.microsoft.com/en-us/graph/throttling). No file mutation endpoint belongs in a connector's transport allowlist.

## Durable processing and PyFly ownership

koinon owns the concrete SharePoint, OneDrive and Google Drive adapters, provider-specific DTOs and ports, delegated consent policy and connected-account lifecycle, mapping review, project authority, source-version bindings, ingestion orchestration, user journeys and audit. These integrations live in `koinon.integrations.content_sources`. PyFly supplies existing generic native HTTP/OAuth acquisition, DI, repositories, scheduling, bounded concurrency and transactional outbox primitives; it does not own product-specific source adapters or mapping rules. Use native DI beans, repositories and configuration properties with DTOs, mappers, services and controllers in separate modules.

The implementation must follow this reuse boundary. A product policy wrapper does not replace the native mechanism underneath it.

| Existing native mechanism | Product responsibility |
| --- | --- |
| `StreamingHttpClientPort`, bounded requests and `HttpxClientAdapter` streaming | Fixed provider hosts, read-only methods, redirect credential isolation, bounded source metadata and staged originals |
| `OAuth2Client.exchange_code`, `refresh_token` and PKCE | Separate delegated content consent, exact installation client binding, read-only scope ceiling, single-use callback state and durable refresh CAS |
| `JWKSTokenValidator` and native `SessionStore` | Verify the content grant issuer, audience, nonce and stable provider subject; recheck the same live application session without borrowing its login tokens |
| Native repositories and primary transaction units | Personal owner/tenant predicates, encrypted grants, short reservation and completion units around provider I/O |
| Native database/PostgreSQL scheduler leases and distributed locks | Mapping schedule identity, due work, ownership fences and checkpoint policy; no separate scheduler subsystem |
| Native SQL/Mongo transactional outbox | Durable source observations and ingestion admission; no separate delivery queue subsystem |
| `koinon_storage.client_lifecycle.ClientLifecycle` | Close only owned clients after active requests drain |

The small generic PyFly dependency change exposes typed streaming responses, public OAuth URI/scope validation and read-only client identity, plus opt-in inherited-credential suppression and sanitized transport failures. It does not contain SharePoint, OneDrive or Google Drive adapters. Until that dependency is released and pinned, source-override tests are development evidence only. The native device flow is available but is not a substitute for this browser-bound consent journey.

The existing PyFly `ContentSource` contract describes changed files and a local `Path`; it does not express deleted objects, permission loss, typed change pages or streaming into configured storage. Define the typed change-page, provider identity and streaming-staging contracts in the product rather than manufacturing zero-byte files for deletions or putting an entire downloaded file in memory. Reuse generic native streaming response ports and OAuth clients; preserve existing framework source implementations and their cursor behavior. Do not call an optional SharePoint example a shipped adapter.

Store source connections, revisioned mappings, run records, change observations, per-item attempts and origin bindings in typed primary repositories. Keep secrets outside these DTOs and public snapshots. A change observation records provider/account/drive/object IDs, remote version, mapping revision, event kind and an immutable operation key. The origin binding records koinon source/asset/version IDs, downloaded hash and bytes, transformation details and commit receipt.

Workers follow short database units: reserve a bounded lease, perform remote I/O without holding a database connection, persist the observation and enqueue ingestion atomically through the outbox, then acknowledge the checkpoint. A persisted observation is not a claim that ingestion succeeded. The run reports discovery, transfer and indexing checkpoints independently. Job retries reuse the exact operation identity and native receipts; unknown publication outcomes enter reconciliation instead of creating a second source.

Assign each origin object a monotonic observation generation and use compare-and-swap at publication against its latest admitted observation, mapping revision and local retirement state. A slow older download or parser must not replace a newer published version or resurrect a deletion or exclusion. Provider feeds can repeat an object within a delta sequence; retain page order and reconcile its final observed state before completing that sequence. A mapping lease alone does not order different versions of one object.

Use per-provider, per-account, per-installation and worker limits. Lease heartbeats and fencing prevent a superseded worker from advancing a cursor or publishing a version. Restart tests must cover every boundary between byte storage, queue admission, native commit and acknowledgement. The scheduler must not create duplicate runs for an already active mapping. Pausing stops new admissions; safe in-flight work finishes or cancels under existing lease rules.

## Internal destination and overlap review

The current internal review service accepts explicit connection, drive, source-folder and existing Library destination IDs. It calls the canonical `BulkAuthority.destination` policy before provider reads and again before persistence. It neither enumerates the rest of the Library nor creates a fallback folder. A valid source connection does not grant Library write permission. This uses the current Library workspace and resource policy; it does not introduce project ACLs.

The current bulk destination contract accepts a collection/corpus folder directly under its project. Library itself can contain nested folders, but those nested destinations are rejected by this review before provider I/O. The supplied destination is never silently replaced with a project-level parent. Supporting nested sync destinations requires a separately reviewed canonical intake ancestry change; it is not delivered by this checkpoint.

Overlap admission compares non-retired mappings for the exact organization, provider, verified external account/tenant and drive. Expired inactive reviews are excluded. Only IDs, revisions and selection policy enter the private comparison; responses expose no other owner's mapping, destination or remote title. Equality conflicts; an ancestor conflicts only when its selection is recursive. Account-scoped checks do not yet establish cross-account equivalence of shared provider objects. That remains an activation gate, not a claim that two different connected accounts cannot overlap.

Two fresh metadata passes resolve the selected and candidate roots to the provider's actual drive root. They reuse shared ancestors within each pass and compare IDs, parents and available versions. Missing parents outside the known drive root, inaccessible ancestors, shortcuts, cycles and multiple-parent ambiguity fail closed. No remote subtree or file enumeration is performed. Consequently, a shared folder whose ancestry cannot be proved to the selected drive root cannot yet be reviewed. These checks observe provider state; they do not lock remote ACLs or folders. Subsequent acceptance and ingestion must revalidate current authority and ancestry rather than treating this review as a reusable grant.

The per-review guardrails are at most 99 existing candidate mappings plus the proposed root, 64 nodes per ancestry path, 512 distinct metadata nodes per pass, two passes, and a 120-second metadata deadline including admission to a four-slot process semaphore. Hitting a guardrail rejects the review; it never truncates candidates and reports no conflict. These are bounded review safeguards, not limits on enterprise corpus size or file count. A more scalable overlap strategy requires separate qualification before activation.

No primary, document or structured unit of work remains open during provider calls. The final short write reacquires canonical tenant/destination authority, locks the current personal connection and checks the captured account, credential revision, scopes and installation configuration. It compares the mapping inventory again before saving an inactive `reviewed` record that expires after 15 minutes. Mapping admission and future revision/retirement writers must participate in the same canonical tenant serialization. The retained snapshot contains the selected IDs and ancestor IDs, policy, configuration binding, observed connection revision and a proof digest; it contains no credentials or remote titles. The observation's credential revision is review evidence, not permanent origin authorization.

This checkpoint has no public synchronization routes, enabled UI action, remote mutation, durable import, migration execution or publication hook. Native SQLite tests exercise canonical destination denial, late destination/credential/configuration changes, changed ancestry and mapping revisions, overlap, cancellation and private inactive persistence. PostgreSQL opposing-writer tests, cross-account shared-object overlap, complete reader/output fences and real delegated provider qualification remain required before activation.

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

### Current adapter development limits

The internal adapter milestone is not activated in the application and does not provide public synchronization. Installation-owned registrations keep content-consent clients separate from login. An optional `allow_loopback_http` must be a literal boolean and permits only `localhost`, `127.0.0.1` and `::1` callbacks; remote callbacks require HTTPS. Changing registration parameters invalidates pending consent and requires reconnection of an old grant. Refresh stores the effective returned scopes and never requests permissions removed by a previous refresh response.

Metadata requests, connection establishment, idle reads and complete transfers have separate installation deadlines. Defaults are 30, 10, 30 and 900 seconds respectively; the transfer deadline covers redirects and sink writes without restarting. These are development transport bounds, not a worker qualification or a larger ingestion allowance. Every download still requires the effective admitted `max_bytes`; the existing file-intake limits remain authoritative. The future worker must renew and fence its durable lease throughout an admitted transfer.

Graph `/content` accepts direct HTTP 200 streaming without any redirect-host configuration. HTTP 302/307 follows at most one credential-free redirect to an exact installation-approved hostname. An empty allowlist rejects redirects, and wildcards are invalid. This avoids making temporary authenticated URLs mandatory: Microsoft has announced their retirement beginning April 1, 2027. Do not replace the stable API with `contentStream` beta implicitly. See the [Microsoft migration notice](https://devblogs.microsoft.com/microsoft365dev/pre-authenticated-tempauth-urls-are-retiring-move-to-microsoft-entra-id-tokens-before-april-1-2027/).

Google Workspace exports use explicit DOCX/XLSX/PPTX formats and retain the documented 10 MB `files.export` limit. The asynchronous `files.download` POST operation is not implemented by the GET-only content adapter; it requires a separately reviewed durable operation, not arbitrary POST support. See [Google download and export limits](https://developers.google.com/workspace/drive/api/guides/manage-downloads). Provider grants, large-file transfers and export behavior still require real owned-account acceptance before release.

### Complete journey gates

Provide typed endpoints and all supported SDK methods for connection status, source browsing, mapping preview/create/update, run/status/history, pause/resume, synchronization request, exclusions and local retirement. MCP exposes the same operations with explicit narrow scopes and current user identity. An assistant cannot complete external OAuth, approve its own mapping changes, receive refresh credentials or gain source access from the mapping owner.

Qualification includes a completely empty installation, authorized destination creation and the no-permission path without automatic fallback folders. Exercise version2 completing before version1, duplicate object observations, deletion while an earlier parse is running, and expired-cursor recovery interrupted before enumeration completes. Qualification also covers mixed supported/unsupported files, unknown sizes, large originals, Google export limits, partial batches, overlapping roots, rename/move/delete, permission removal, token expiry, invalid continuation links, throttling, restart after every persisted checkpoint, duplicate events, stale mapping revisions, local exclusions and constant bounded query/concurrency behavior. Include two users with different source access, two Library projects, API/MCP equivalence and remembered-output revocation.

Before release, run genuine delegated provider journeys against owned test folders and inspect provider audit/network evidence that no remote files were mutated. A mock adapter or HTTP fixture validates contracts only. Publish step-by-step installation, user connection, mapping, initial import, operation, recovery and uninstallation guides with actual screenshots after those screens exist. Keep source tests, packaged artifacts, hosted CI and live provider acceptance separate.
