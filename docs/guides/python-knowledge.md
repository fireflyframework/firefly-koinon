<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Python: create, read and maintain knowledge

Use the client from the [Python quickstart](headless-python.md). Reading requires the appropriate current catalog permissions; ingestion requires `ingest:write` and its catalog dependencies. A workspace-bound integration can create knowledge only inside an admitted destination. An asset-bound token does not grant arbitrary new upload destinations. See [API permissions](api-permissions.md).

## Create a destination and upload

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
