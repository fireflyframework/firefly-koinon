<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Python: create, read and maintain knowledge

Use the client from the [Python quickstart](headless-python.md). Reading requires the appropriate current catalog permissions; ingestion requires `ingest:write` and its catalog dependencies. A workspace-bound integration can create knowledge only inside an admitted destination. An asset-bound token does not grant arbitrary new upload destinations. See [API permissions](api-permissions.md).

## Follow one asset through its lifecycle

This chapter starts with an existing workspace, creates a destination, uploads one source, and then reads its processing and historical identities. Use a small authorized document first. Repeat the intake decision for a real XLSX or another supported structured file only after you understand the returned receipt. The SDK does not turn arbitrary spreadsheet bytes into an admitted dataset by changing a filename.

You need `catalog:read` for browsing, `ingest:write` and its required catalog scopes for intake, `knowledge:search` for retrieval, and `query:execute` for SQL. Those scopes still intersect with current resource permissions. Use a workspace-bound integration for creating new assets. A token bounded to an existing asset is suitable for that asset's admitted operations, not for creating arbitrary siblings.

[The complete knowledge source](../examples/python/README.md) includes this chapter's helpers, reviewed replacement and append functions, and a read-only history entry point. Set `KOINON_DOCUMENT_ID` to a document selected from the authorized catalog before running that entry point. It prints source-version IDs and SHA256 values; it does not upload or replace anything automatically.

## Run the read-only chapter

Download `support.py` and the selected chapter file into the same directory, then use the Python environment from setup. [Complete source and build instructions](../examples/python/README.md) include [the entry-point file](../examples/python/knowledge.py). This history command additionally needs an authorized `KOINON_DOCUMENT_ID` selected from the catalog. Keep credentials in the approved environment rather than adding them to these commands.

```sh
python knowledge.py
```

The result prints source-version IDs and SHA256 values from the first bounded page. No rows can mean no recorded versions in the authorized scope; preserve missing history instead of inventing a revision. If authorization fails, return to the setup chapter and inspect current context/scopes instead of broadening the request. The remaining helpers define the intended mutations, but this command does not invoke them.

## Create a destination and upload

First choose whether the caller is creating a new destination or reusing an existing one. The example creates a project and collection so the returned parent IDs are concrete. Record both IDs immediately; a later upload failure does not roll those writes back. In a repeatable integration, create the destination once, persist it, and reuse it rather than creating a new project for every file.

The upload's workspace, project, and parent identify the admitted destination. The filename is display metadata; the bytes are the source. Inspect the returned `source.id`, each `assets` entry, and optional `job_id`. Save that receipt before starting another file. If processing is asynchronous, inspect the identified job and resulting asset status before searching or querying the new content. An accepted request is not a completed extraction.


This helper performs writes only when called. Supply an existing authorized workspace and a caller-selected file. Its 32 MiB bound is an application choice; the server also checks configured formats, limits and extractors.

```python
import asyncio
from pathlib import Path
from koinon_sdk import KoinonClient, UploadResponse

async def ingest_document(
    client: KoinonClient, tenant: str, workspace: str, file: Path,
) -> UploadResponse:
    if not file.is_file() or not 0 < file.stat().st_size <= 32 * 1024 * 1024:
        raise ValueError("Choose a nonempty regular file up to 32 MiB")
    content = await asyncio.to_thread(file.read_bytes)
    if not 0 < len(content) <= 32 * 1024 * 1024:
        raise ValueError("The file changed after validation")
    project = await client.create(tenant, kind="project", name="Operations", parent_id=workspace)
    collection = await client.create(tenant, kind="collection", name="Policies", parent_id=project.id)
    await client.update(tenant, collection.id, name="Approved policies")
    return await client.upload(
        tenant, filename=file.name, content=content, workspace_id=workspace,
        project_id=project.id, parent_id=collection.id, mode="document",
    )
```

Use `mode="dataset"` for admitted structured formats. Retain the returned source, asset identities and optional `job_id`; acceptance is not proof that extraction or indexing finished. Inspect `job(tenant, job_id)` when supplied and the resulting catalog status. Do not automatically repeat project creation or upload after a timeout: reconcile the authorized catalog and retained receipts first.

For a bounded multi-file import, create or select the destination once, then call `upload` sequentially with those same authorized project/collection IDs. Persist each receipt before advancing and cap the application's file count and per-file bytes. Stop after an ambiguous outcome and reconcile that file. This is a caller-owned loop, not an atomic batch, background recovery API or automatic retry of the list.

`update` changes catalog names, descriptions and metadata. `archive` and `restore` are explicit reversible operations. `delete` is a separate destructive catalog request with current ancestry and dependency checks; it is not a curated-item deletion API. `append_dataset_file` adds one file to an existing dataset with a caller-owned stable `idempotency_key`. Persist that key with the exact bytes and receipt. A changed payload conflicts, and a pending outcome needs reconciliation rather than a new key or a replayed batch.

## Import an XLSX as a dataset

Select `dataset` intake for a supported workbook. Keep the original filename and bytes, and choose the same authorized destination deliberately. Call `upload` with `mode="dataset"`, as in the complete helper below. The destination IDs have the same meaning as the document example.

The destination below already exists. Supply a real supported workbook selected by the person; keep the returned receipt before processing another file.

```python
import asyncio
from pathlib import Path
from koinon_sdk import KoinonClient, UploadResponse

async def ingest_dataset(
    client: KoinonClient, tenant: str, workspace: str, project_id: str,
    collection_id: str, file: Path,
) -> UploadResponse:
    if not file.is_file() or not 0 < file.stat().st_size <= 32 * 1024 * 1024:
        raise ValueError("Choose a nonempty regular file up to 32 MiB")
    content = await asyncio.to_thread(file.read_bytes)
    if not 0 < len(content) <= 32 * 1024 * 1024:
        raise ValueError("The file changed after validation")
    return await client.upload(
        tenant, filename=file.name, content=content, workspace_id=workspace,
        project_id=project_id, parent_id=collection_id, mode="dataset",
    )
```

After processing, call `schema` with the **returned dataset asset ID**. Inspect the returned tables and columns before writing SQL. A workbook can produce multiple tables; the source catalog ID, dataset asset ID, table ID, catalog file-version ID, and immutable table snapshot ID serve different purposes. Do not assume the upload source is itself the SQL dataset or manufacture table IDs from sheet labels.

Append another supported file with `append_dataset_file` only after the person has selected the existing dataset and the exact file. Generate and durably retain one idempotency key for that intended append before sending it. Keep that key bound to the same bytes and destination. Save the returned file-version and table IDs. A pending or unknown result needs reconciliation; changing the key does not turn it into a new safe attempt.

Replacing a table requires its current snapshot precondition, while appending adds a file. Replacing a document requires its original digest and, when supplied, its matching source-version/extraction pair. These are different user decisions. Use the complete source's append and replacement helpers rather than using catalog metadata updates as a content upload.

## Search and query the admitted scope

```python
from koinon_sdk import KoinonClient, SearchResponse, QueryResponse

async def retrieve(
    client: KoinonClient, tenant: str, workspace: str, dataset_id: str, sql: str,
) -> tuple[SearchResponse, QueryResponse]:
    hits = await client.search(
        tenant, "Retention policy", workspace_id=workspace, limit=10, answer=False,
    )
    query = await client.query(tenant, dataset_id, sql=sql)
    return hits, query
```

Discover actual table and column names with `schema`, then supply the intended bounded SQL to the helper. `knowledge:search` and `query:execute` remain separate permissions. Explicit SQL still passes through server authorization and its read-only firewall. Inspect `execution_status`, `truncated` and `snapshot_pins`; a preview is not the full result. Exact decimal and unsafe-integer cells remain strings. Do not round them through `float`.

Search hits may carry an immutable `source_reference`. Older hits may omit it. Never fabricate a historical reference from a document's current head. Read the [knowledge runtime explanation](../concepts/knowledge-runtime.md) for retrieval, embeddings, RAG and RLM behavior; choosing a client method does not configure a provider or prove model execution.

## Read the exact document version

The history API separates raw versions, extractions and parts. Pass identities returned by the preceding level instead of mixing a historical version with a current extraction.

```python
from koinon_sdk import KoinonClient, DocumentPartContent

async def first_recorded_chunk(
    client: KoinonClient, tenant: str, document_id: str,
) -> DocumentPartContent | None:
    versions = await client.document_versions(tenant, document_id, page=1, page_size=25)
    if not versions.items:
        return None
    version = versions.items[0]
    extractions = await client.document_extractions(
        tenant, document_id, version.source_version_id, page=1, page_size=25,
    )
    if not extractions.items:
        return None
    extraction = extractions.items[0]
    parts = await client.document_parts(
        tenant, document_id, version.source_version_id, extraction.extraction_id,
        kind="chunk", page=1, page_size=25,
    )
    if not parts.items:
        return None
    return await client.document_part(
        tenant, document_id, version.source_version_id, extraction.extraction_id,
        parts.items[0].source_part_id,
    )
```

`document_version_original` returns a private `BinaryDownload` for that exact raw version. All historical reads recheck current authority; possession of an old ID is not continuing access. Preserve hashes, nullable page metadata and `page_basis`; a loader-recorded page is different from an invented page number.

For tables, use `table_snapshots` and its separate `current_snapshot_id`, then `table_provenance` or coordinate helpers with the exact selected `snapshot_id`. `file_section` provenance does not establish cell-level coverage. Null origins remain unknown.

Replacement is an explicit write: `replace_document`/`reingest_document` need the current unquoted `expected_sha256`; supply `expected_source_version_id` and `expected_extraction_id` together when binding a recorded head. Chunk invalidation acknowledgment defaults to false. Table replacement/reingestion needs `expected_snapshot_id`. The SDK quotes `If-Match`; a conflict requires reloading and reviewing the new state, never forcing an overwrite.

## Connect retrieval, SQL and lineage

Start retrieval with a question and the chosen workspace; keep `answer=false` when you want matching passages without a generated answer. Check hit references and scores before asking for generation. Retrieval can still use a configured embedding service, so an error here may be a configuration/provider failure rather than an empty result. Do not remove scope filters to hide that failure.

For structured data, inspect the schema, choose one actual dataset, and submit bounded read-only SQL using its real table and column names. Use a small row limit appropriate to your task. Inspect `execution_status`, truncation and immutable snapshot pins before displaying the result as complete. An authorization or SQL-firewall rejection must be corrected explicitly; the SDK does not run arbitrary SQL against the original upstream database.

Call `lineage` for the selected catalog asset to read its currently authorized relationships. For document evidence, follow source version, extraction and part IDs. For table evidence, select a recorded snapshot before reading provenance or coordinates. A relationship edge explains a recorded connection; it is not proof that every cell has a known origin. Leave unavailable or unrecorded identities unknown.

## Decide what to do after a content change

Present the current digest/snapshot and the effects of replacement before asking for confirmation. The reviewed replacement helper takes the already reviewed identities; it does not silently read a newer revision and overwrite it. A conflict means the user must inspect the new head and make another decision. Keep invalidation acknowledgment false until the user understands the affected chunks or dependencies.

After success, retain `ContentUpdate.asset`, `version`, and `effects`. Reload the current catalog and inspect its new native history before using old chunk or snapshot IDs as current. Historical IDs remain historical even when the asset name is unchanged. If a write times out, reconcile the saved operation and current state first; a missing HTTP response does not prove that no change occurred.

## Review curated knowledge before committing

`preview_knowledge` creates an owner-scoped intent, not a repository write. Show its destination, `before`/`after`, evidence, revision and status to the person. A separate confirmation action must use the exact reviewed revision and digest.

```python
from koinon_sdk import (
    KoinonClient, KnowledgeConfirmation, KnowledgeIntent, KnowledgeCommitOutcome,
    KnowledgeIntentInput, KnowledgeContent, UserStatementOrigin,
)

async def preview_draft(
    client: KoinonClient, tenant: str, destination_id: str, title: str, user_body: str,
) -> KnowledgeIntent:
    return await client.preview_knowledge(tenant, KnowledgeIntentInput(
        action="create_draft", destination_id=destination_id,
        content=KnowledgeContent(title=title, body=user_body),
        origin=UserStatementOrigin(kind="user_statement"),
    ))

async def confirm_reviewed_intent(
    client: KoinonClient, tenant: str, reviewed: KnowledgeIntent,
    user_confirmed: bool, stable_key: str,
) -> KnowledgeCommitOutcome:
    if not user_confirmed or reviewed.status != "preview":
        raise ValueError("Review the current intent and confirm it explicitly")
    return await client.confirm_knowledge(
        tenant, reviewed.id,
        KnowledgeConfirmation(confirm=True, expected_revision=reviewed.revision,
                              authorization_digest=reviewed.authorization_digest),
        idempotency_key=stable_key,
    )
```

The example's body must be an actual user statement; do not relabel imported or model-generated content as user-authored evidence. Use the matching conversation or external-review origin instead. Updates and publishing must carry the intended target and its expected version. `knowledge_items`, `knowledge_item` and `knowledge_version` read serving and historical versions. A draft preserves the published serving version. A `pending` commit is unresolved; retain its operation identity and reconcile it. Never automatically confirm a model suggestion, infer human consent, or invent a curated delete/share/export/derive capability. See [reviewed external changes](mcp-knowledge-management.md) and the [generated API reference](../reference/sdk-api.md).
