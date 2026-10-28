<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# koinon headless SDKs

Use the authenticated knowledge API from Python, TypeScript or Java. The clients support typed requests and responses, file uploads, paginated reads, conversation streaming and recorded source provenance. The backend enforces membership, token scopes and resource permissions on every request.

| Client | Package | Guide |
|---|---|---|
| Python | `firefly-koinon-sdk` | [Async client](python/README.md) |
| TypeScript | `@fireflyframework/koinon-sdk` | [Browser and server transports](typescript/README.md) |
| Java | `org.fireflyframework:koinon-sdk` | [Java 21 client](java/README.md) |

Start with the [headless integration guide](../docs/guides/headless.md). The [shared contract](contract/operations.json) records canonical operations; the [API reference](../docs/reference/sdk-api.md) describes their typed models and methods. Keep tokens in a host-supplied callback and let the host handle renewal. Writes are not automatically retried.

These are development packages. Source tests, installed-package checks, server integration and publication are separate acceptance steps. See the [qualification record](../docs/operations/qualification.md) before rollout.

All three clients use [Apache-2.0](../LICENSE).


Catalog pages include optional typed `summaries` keyed by entry ID, alongside the existing public `actors` map. Library folder counts cover the complete visible child projection, including files beneath source wrappers, before pagination. Counts honor the caller's current workspace, project and token resource boundaries. Archived descendants are excluded unless requested. Dataset `table_count` counts visible table entries. File `size_bytes`, `page_count`, `row_count` and `column_count` use recorded public metadata. Documents may inherit their visible source file size; datasets require a recorded dataset-level size and never inherit original source bytes; unknown values are null, not zero. Historical estimates are not promoted to exact row counts.

Use `format="pdf"` and `tag="reviewed"` in Python, `{format:'pdf', tag:'reviewed'}` in TypeScript, or `CatalogFilter.empty().withFormat("pdf").withTag("reviewed")` in Java. The server applies exact, trimmed, lowercase filters before totals and pagination. Tags derive from a recognized format, recorded language and string entries in public `metadata.tags`. Custom tag labels preserve their display case and acronyms, with case-insensitive deduplication; no model is invoked and no metadata is written. Format recognizes public `metadata.format`, public `metadata.media_type` and known filename extensions for documents, datasets and sources, in that order. Folder names never imply a file format. Unknown formats stay null. Choose `sort="name"`, `"kind"`, `"created_at"` or `"updated_at"`, with `order="asc"` or `"desc"`; the server uses stable name/ID tie breaking and keeps folders first. Pages are bounded to 1–100 entries.
