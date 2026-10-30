<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# TypeScript: create, read and maintain knowledge

Start with the [framework-neutral TypeScript client](headless-typescript.md). An ingestion integration needs `ingest:write`, its catalog dependencies and current write authority in the destination. A workspace-bound token can create admitted resources there; an asset-bound token does not admit arbitrary new destinations. See [API permissions](api-permissions.md).

## Create a destination and upload

The helper performs writes only when called. Supply a caller-selected `File` and an existing authorized workspace. The 32 MiB bound is this application's limit; the server also enforces supported formats, limits and extractors.

```typescript
import {KoinonClient, type UploadResponse} from '@fireflyframework/koinon-sdk';

export async function ingestDocument(
  client: KoinonClient, tenant: string, workspace: string, file: File,
): Promise<UploadResponse> {
  if (file.size === 0 || file.size > 32 * 1024 * 1024) {
    throw new Error('Choose a nonempty file up to 32 MiB');
  }
  const project = await client.catalog.create(tenant,
    {kind: 'project', name: 'Operations', parent_id: workspace});
  const collection = await client.catalog.create(tenant,
    {kind: 'collection', name: 'Policies', parent_id: project.id});
  await client.catalog.update(tenant, collection.id, {name: 'Approved policies'});
  return client.sources.uploadFile(tenant, {
    file, filename: file.name, workspace_id: workspace, project_id: project.id,
    parent_id: collection.id, mode: 'document',
  });
}
```

Use `mode: 'dataset'` for admitted structured formats. The transport builds multipart fields and preserves the browser's boundary; do not set `Content-Type` yourself. Retain source/asset identities and `job_id` if supplied. Request acceptance is distinct from completed extraction and indexing. Inspect `jobs.get` and resulting catalog status.

For a bounded multi-file import, select/create the destination once and call `sources.uploadFile` sequentially with the same authorized project/collection IDs. Persist each receipt before advancing and bound the application's file count and per-file bytes. Stop and reconcile an ambiguous file outcome. The loop does not provide an atomic batch, background recovery or an automatic replay of the list.

`catalog.update` changes names, descriptions and metadata. `archive`/`restore` are explicit reversible requests. `catalog.delete` is a separate destructive operation with current ancestry/dependency checks, not a curated-item deletion API. `dataset.appendFile` adds one file to an existing dataset with an explicit stable idempotency key. Preserve the key, exact payload and receipt. Pending or failed intake needs reconciliation; a client loop is neither an atomic batch nor a durable recovery process.

## Search and query the admitted scope

```typescript
import {KoinonClient} from '@fireflyframework/koinon-sdk';

export async function retrieve(
  client: KoinonClient, tenant: string, workspace: string, datasetId: string, sql: string,
  signal?: AbortSignal,
) {
  const hits = await client.search(tenant,
    {question: 'Retention policy', workspace_id: workspace, limit: 10, answer: false}, {signal});
  const query = await client.query(tenant,
    {dataset_id: datasetId, sql}, {signal});
  return {hits, query};
}
```

Discover actual table and column names with `dataset.schema`, then supply the intended bounded SQL to the helper. `knowledge:search` and `query:execute` are separate permissions. The server applies authorization and the read-only SQL firewall to explicit SQL as well. Check `execution_status`, `truncated` and `snapshot_pins`; the preview is not the complete result. Exact decimals and unsafe integers remain strings; do not coerce them to `number`.

New search hits can include an immutable `source_reference`; historical hits may omit it. Never reconstruct an old reference from a current head. The [knowledge runtime guide](../concepts/knowledge-runtime.md) explains embeddings, retrieval, RAG and RLM. A selected client helper does not configure a provider or prove a model call.

## Follow version, extraction and part identities

```typescript
import {KoinonClient, type DocumentPartContent} from '@fireflyframework/koinon-sdk';

export async function firstRecordedChunk(
  client: KoinonClient, tenant: string, documentId: string,
): Promise<DocumentPartContent | undefined> {
  const versions = await client.documents.versions(tenant, documentId, {page: 1, page_size: 25});
  const version = versions.items[0];
  if (!version) return;
  const extractions = await client.documents.extractions(
    tenant, documentId, version.source_version_id, {page: 1, page_size: 25});
  const extraction = extractions.items[0];
  if (!extraction) return;
  const parts = await client.documents.parts(tenant, documentId,
    version.source_version_id, extraction.extraction_id, {kind: 'chunk', page: 1, page_size: 25});
  const part = parts.items[0];
  if (!part) return;
  return client.documents.part(tenant, documentId, version.source_version_id,
    extraction.extraction_id, part.source_part_id);
}
```

`documents.versionOriginal` returns a private `BinaryDownload` for that raw version. Each read rechecks current authority. Preserve the returned hashes, nullable page metadata and `page_basis`; possession of an old ID does not grant access or prove a page number.

For tables, use `dataset.tableSnapshots` and its separate `current_snapshot_id`, then `tableProvenance` or coordinate reads with the exact selected snapshot. `file_section` coverage is not cell lineage; unknown origins remain null.

`documents.replace`/`reingest` require the current unquoted `expected_sha256`. Bind `expected_source_version_id` and `expected_extraction_id` together when supplying a recorded head. Chunk invalidation acknowledgment defaults to false and must be explicit when required. Table replacement/reingestion uses `expectedSnapshotId`. The SDK quotes `If-Match`; reload and review after conflicts instead of forcing an overwrite.

## Confirm curated knowledge only after review

`knowledgeIntents.preview` creates a private preview. Show its destination, before/after content, evidence, revision and status to the person. Confirmation is a separate explicit action:

```typescript
import {KoinonClient, type KnowledgeIntent} from '@fireflyframework/koinon-sdk';

export async function previewDraft(
  client: KoinonClient, tenant: string, destinationId: string, title: string, userBody: string,
) {
  return client.knowledgeIntents.preview(tenant, {
    action: 'create_draft', destination_id: destinationId,
    content: {title, body: userBody}, origin: {kind: 'user_statement'},
  });
}

export async function confirmReviewedIntent(
  client: KoinonClient, tenant: string, reviewed: KnowledgeIntent,
  userConfirmed: boolean, stableKey: string,
) {
  if (!userConfirmed || reviewed.status !== 'preview') {
    throw new Error('Review the current intent and confirm it explicitly');
  }
  return client.knowledgeIntents.confirm(tenant, reviewed.id, {
    confirm: true, expected_revision: reviewed.revision,
    authorization_digest: reviewed.authorization_digest,
  }, stableKey);
}
```

The example's body must be an actual user statement. Do not relabel imported/model-generated content as user-authored evidence; use its matching conversation or external-review origin. Updates and publishing carry the target and its expected version. `knowledgeItems.list/get/version` read serving and historical versions; drafts preserve the published serving version. A `pending` result is unresolved: retain its operation identity and reconcile it. Do not infer consent from a model suggestion or invent curated delete/share/export/derive helpers. External MCP reviews have their own receipt and component-only approval rules. See the [generated reference](../reference/sdk-api.md) and [MCP review guide](mcp-knowledge-management.md).
