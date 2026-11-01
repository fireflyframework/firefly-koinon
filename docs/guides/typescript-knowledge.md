<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# TypeScript: create, read and maintain knowledge

Start with the [framework-neutral TypeScript client](headless-typescript.md). An ingestion integration needs `ingest:write`, its catalog dependencies and current write authority in the destination. A workspace-bound token can create admitted resources there; an asset-bound token does not admit arbitrary new destinations. See [API permissions](api-permissions.md).

## Follow one asset through its lifecycle

This chapter starts with an existing workspace, creates a destination, uploads one source, and then reads its processing and historical identities. Use a small authorized document first. Repeat the intake decision for a real XLSX or another supported structured file only after you understand the returned receipt. The SDK does not turn arbitrary spreadsheet bytes into an admitted dataset by changing a filename.

You need `catalog:read` for browsing, `ingest:write` and its required catalog scopes for intake, `knowledge:search` for retrieval, and `query:execute` for SQL. Those scopes still intersect with current resource permissions. Use a workspace-bound integration for creating new assets. A token bounded to an existing asset is suitable for that asset's admitted operations, not for creating arbitrary siblings.

[The complete knowledge source](../examples/typescript/README.md) includes this chapter's helpers, reviewed replacement and append functions, and a read-only history entry point. Set `KOINON_DOCUMENT_ID` to a document selected from the authorized catalog before running that entry point. It prints source-version IDs and SHA256 values; it does not upload or replace anything automatically.

## Run the read-only chapter

Download `support.mts`, the selected chapter module and `tsconfig.json` together, then use the Node package from setup. [Complete source and build instructions](../examples/typescript/README.md) include [the entry-point file](../examples/typescript/knowledge.mts). This history command additionally needs an authorized `KOINON_DOCUMENT_ID` selected from the catalog. Keep credentials in the approved environment rather than adding them to these commands.

```sh
npx tsc -p tsconfig.json
node dist/knowledge.mjs
```

The result prints source-version IDs and SHA256 values from the first bounded page. No rows can mean no recorded versions in the authorized scope; preserve missing history instead of inventing a revision. If authorization fails, return to the setup chapter and inspect current context/scopes instead of broadening the request. The remaining helpers define the intended mutations, but this command does not invoke them.

## Create a destination and upload

First choose whether the caller is creating a new destination or reusing an existing one. The example creates a project and collection so the returned parent IDs are concrete. Record both IDs immediately; a later upload failure does not roll those writes back. In a repeatable integration, create the destination once, persist it, and reuse it rather than creating a new project for every file.

The upload's workspace, project, and parent identify the admitted destination. The filename is display metadata; the bytes are the source. Inspect the returned `source.id`, each `assets` entry, and optional `job_id`. Save that receipt before starting another file. If processing is asynchronous, inspect the identified job and resulting asset status before searching or querying the new content. An accepted request is not a completed extraction.


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

For saved multi-file manifests, bounded uploads and per-file recovery, use [durable bulk intake](bulk-intake.md). A sequential `sources.uploadFile` loop remains caller-owned: persist receipts, bound its files and reconcile ambiguous outcomes. It does not make the list atomic.

`catalog.update` changes names, descriptions and metadata. `archive`/`restore` are explicit reversible requests. `catalog.delete` is a separate destructive operation with current ancestry/dependency checks, not a curated-item deletion API. `dataset.appendFile` adds one file to an existing dataset with an explicit stable idempotency key. Preserve the key, exact payload and receipt. Pending or failed intake needs reconciliation; a client loop is neither an atomic batch nor a durable recovery process.

## Import an XLSX as a dataset

Select `dataset` intake for a supported workbook. Keep the original filename and bytes, and choose the same authorized destination deliberately. Set `mode: 'dataset'` in `sources.uploadFile`, as in the complete helper below. The destination IDs have the same meaning as the document example.

The helper reuses the existing destination. A host can construct a `File` from caller-selected bytes; do not treat an extension as proof of the file's format.

```typescript
import {KoinonClient, type UploadResponse} from '@fireflyframework/koinon-sdk';

export async function ingestDataset(
  client: KoinonClient, tenant: string, workspace: string,
  projectId: string, collectionId: string, file: File,
): Promise<UploadResponse> {
  if (!file.size || file.size > 32 * 1024 * 1024) {
    throw new Error('Choose a nonempty file up to 32 MiB');
  }
  return client.sources.uploadFile(tenant, {
    file, filename: file.name, workspace_id: workspace,
    project_id: projectId, parent_id: collectionId, mode: 'dataset',
  });
}
```

After processing, call `dataset.schema` with the **returned dataset asset ID**. Inspect the returned tables and columns before writing SQL. A workbook can produce multiple tables; the source catalog ID, dataset asset ID, table ID, catalog file-version ID, and immutable table snapshot ID serve different purposes. Do not assume the upload source is itself the SQL dataset or manufacture table IDs from sheet labels.

Append another supported file with `dataset.appendFile` only after the person has selected the existing dataset and the exact file. Generate and durably retain one idempotency key for that intended append before sending it. Keep that key bound to the same bytes and destination. Save the returned file-version and table IDs. A pending or unknown result needs reconciliation; changing the key does not turn it into a new safe attempt.

Replacing a table requires its current snapshot precondition, while appending adds a file. Replacing a document requires its original digest and, when supplied, its matching source-version/extraction pair. These are different user decisions. Use the complete source's append and replacement helpers rather than using catalog metadata updates as a content upload.

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

## Connect retrieval, SQL and lineage

Start retrieval with a question and the chosen workspace; keep `answer=false` when you want matching passages without a generated answer. Check hit references and scores before asking for generation. Retrieval can still use a configured embedding service, so an error here may be a configuration/provider failure rather than an empty result. Do not remove scope filters to hide that failure.

For structured data, inspect the schema, choose one actual dataset, and submit bounded read-only SQL using its real table and column names. Use a small row limit appropriate to your task. Inspect `execution_status`, truncation and immutable snapshot pins before displaying the result as complete. An authorization or SQL-firewall rejection must be corrected explicitly; the SDK does not run arbitrary SQL against the original upstream database.

Call `lineage` for the selected catalog asset to read its currently authorized relationships. For document evidence, follow source version, extraction and part IDs. For table evidence, select a recorded snapshot before reading provenance or coordinates. A relationship edge explains a recorded connection; it is not proof that every cell has a known origin. Leave unavailable or unrecorded identities unknown.

## Decide what to do after a content change

Present the current digest/snapshot and the effects of replacement before asking for confirmation. The reviewed replacement helper takes the already reviewed identities; it does not silently read a newer revision and overwrite it. A conflict means the user must inspect the new head and make another decision. Keep invalidation acknowledgment false until the user understands the affected chunks or dependencies.

After success, retain `ContentUpdate.asset`, `version`, and `effects`. Reload the current catalog and inspect its new native history before using old chunk or snapshot IDs as current. Historical IDs remain historical even when the asset name is unchanged. If a write times out, reconcile the saved operation and current state first; a missing HTTP response does not prove that no change occurred.

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

When a conversation-origin intent reports `remembered_context_present`, show the remembered-context explanation alongside the exact intent preview and obtain a separate decision. Only an explicit approval permits `include_remembered_context=true` on `KnowledgeConfirmation` (Java: `withIncludeRememberedContext(true)`). The examples above leave that consent disabled. Evidence marked `basis: remembered_context` remains attributed to its recorded historical source rather than being presented as new retrieval. See [conversation memory](conversation-memory.md#share-or-publish-an-answer-that-used-memory) for the complete behavior.

## Move an organizational folder

Read the folder immediately before asking the person to confirm its destination. Retain the exact parent and timestamp returned by the server. This helper sends one requested move and leaves conflicts visible to the caller.

```typescript
import {KoinonClient, type CatalogEntry} from '@fireflyframework/koinon-sdk';

export function moveFolder(
  client: KoinonClient, tenant: string, folder: CatalogEntry, destinationId: string,
): Promise<CatalogEntry> {
  if (folder.parent_id === null || !folder.updated_at) {
    throw new Error('Read the current folder location and update timestamp first');
  }
  return client.catalog.move(tenant, folder.id, {
    parent_id: destinationId,
    expected_parent_id: folder.parent_id,
    expected_updated_at: folder.updated_at,
  });
}
```

`system_managed` identifies retained installation defaults; it is an output, never an editable metadata flag. The backend protects those folders even if a host omits the interface check. Ordinary collection and corpus folders move only inside the same project and space. Handle `CATALOG_CHANGED` by reloading and reviewing a new decision. `KNOWLEDGE_TRANSFER_REQUIRED` means the request crosses a boundary that this move operation cannot change. See [Library hierarchy and permissions](library.md#spaces-projects-and-folders).
