# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import asyncio
from pathlib import Path

from koinon_sdk import (
    ContentUpdate,
    DatasetFileAppendResult,
    DocumentChunks,
    DocumentPartContent,
    DocumentVersion,
    KnowledgeCommitOutcome,
    KnowledgeConfirmation,
    KnowledgeContent,
    KnowledgeIntent,
    KnowledgeIntentInput,
    KoinonClient,
    QueryResponse,
    SearchResponse,
    TableProvenance,
    UploadResponse,
    UserStatementOrigin,
)
from support import connect, required


async def ingest_document(
    client: KoinonClient,
    tenant: str,
    workspace: str,
    file: Path,
) -> UploadResponse:
    if not file.is_file() or not 0 < file.stat().st_size <= 32 * 1024 * 1024:
        raise ValueError("Choose a nonempty regular file up to 32 MiB")
    content = await asyncio.to_thread(file.read_bytes)
    if not 0 < len(content) <= 32 * 1024 * 1024:
        raise ValueError("The file changed after validation")
    project = await client.create(
        tenant, kind="project", name="Operations", parent_id=workspace
    )
    collection = await client.create(
        tenant, kind="collection", name="Policies", parent_id=project.id
    )
    await client.update(tenant, collection.id, name="Approved policies")
    return await client.upload(
        tenant,
        filename=file.name,
        content=content,
        workspace_id=workspace,
        project_id=project.id,
        parent_id=collection.id,
        mode="document",
    )


async def retrieve(
    client: KoinonClient,
    tenant: str,
    workspace: str,
    dataset_id: str,
    sql: str,
) -> tuple[SearchResponse, QueryResponse]:
    hits = await client.search(
        tenant,
        "Retention policy",
        workspace_id=workspace,
        limit=10,
        answer=False,
    )
    query = await client.query(tenant, dataset_id, sql=sql)
    return hits, query


async def first_recorded_chunk(
    client: KoinonClient,
    tenant: str,
    document_id: str,
) -> DocumentPartContent | None:
    versions = await client.document_versions(tenant, document_id, page=1, page_size=25)
    if not versions.items:
        return None
    version = versions.items[0]
    extractions = await client.document_extractions(
        tenant,
        document_id,
        version.source_version_id,
        page=1,
        page_size=25,
    )
    if not extractions.items:
        return None
    extraction = extractions.items[0]
    parts = await client.document_parts(
        tenant,
        document_id,
        version.source_version_id,
        extraction.extraction_id,
        kind="chunk",
        page=1,
        page_size=25,
    )
    if not parts.items:
        return None
    return await client.document_part(
        tenant,
        document_id,
        version.source_version_id,
        extraction.extraction_id,
        parts.items[0].source_part_id,
    )


async def preview_draft(
    client: KoinonClient,
    tenant: str,
    destination_id: str,
    title: str,
    user_body: str,
) -> KnowledgeIntent:
    return await client.preview_knowledge(
        tenant,
        KnowledgeIntentInput(
            action="create_draft",
            destination_id=destination_id,
            content=KnowledgeContent(title=title, body=user_body),
            origin=UserStatementOrigin(kind="user_statement"),
        ),
    )


async def confirm_reviewed_intent(
    client: KoinonClient,
    tenant: str,
    reviewed: KnowledgeIntent,
    user_confirmed: bool,
    stable_key: str,
) -> KnowledgeCommitOutcome:
    if not user_confirmed or reviewed.status != "preview":
        raise ValueError("Review the current intent and confirm it explicitly")
    return await client.confirm_knowledge(
        tenant,
        reviewed.id,
        KnowledgeConfirmation(
            confirm=True,
            expected_revision=reviewed.revision,
            authorization_digest=reviewed.authorization_digest,
        ),
        idempotency_key=stable_key,
    )


async def append_reviewed_file(
    client: KoinonClient,
    tenant: str,
    dataset_id: str,
    file: Path,
    stable_key: str,
    person_confirmed: bool,
) -> DatasetFileAppendResult:
    if not person_confirmed:
        raise ValueError("Review the dataset, file and stable key first")
    if not file.is_file() or not 0 < file.stat().st_size <= 32 * 1024 * 1024:
        raise ValueError("Choose a nonempty regular file up to 32 MiB")
    content = await asyncio.to_thread(file.read_bytes)
    if not 0 < len(content) <= 32 * 1024 * 1024:
        raise ValueError("The file changed after validation")
    return await client.append_dataset_file(
        tenant,
        dataset_id,
        filename=file.name,
        content=content,
        idempotency_key=stable_key,
    )


async def replace_reviewed_document(
    client: KoinonClient,
    tenant: str,
    document_id: str,
    original: DocumentVersion,
    head: DocumentChunks,
    content: bytes,
    filename: str,
    person_confirmed: bool,
) -> ContentUpdate:
    if (
        not person_confirmed
        or not head.extraction_id
        or original.source_version_id != head.source_version_id
    ):
        raise ValueError("Review the matching original and extraction head")
    if not 0 < len(content) <= 32 * 1024 * 1024:
        raise ValueError("Choose replacement bytes up to 32 MiB")
    return await client.replace_document(
        tenant,
        document_id,
        filename=filename,
        content=content,
        expected_sha256=original.sha256,
        expected_source_version_id=original.source_version_id,
        expected_extraction_id=head.extraction_id,
        acknowledge_chunk_invalidation=True,
    )


async def inspect_table_origin(
    client: KoinonClient,
    tenant: str,
    dataset_id: str,
    table_id: str,
    selected_snapshot_id: str,
) -> TableProvenance:
    return await client.table_provenance(
        tenant,
        dataset_id,
        table_id,
        snapshot_id=selected_snapshot_id,
    )


async def ingest_dataset(
    client: KoinonClient,
    tenant: str,
    workspace: str,
    project_id: str,
    collection_id: str,
    file: Path,
) -> UploadResponse:
    if not file.is_file() or not 0 < file.stat().st_size <= 32 * 1024 * 1024:
        raise ValueError("Choose a nonempty regular file up to 32 MiB")
    content = await asyncio.to_thread(file.read_bytes)
    if not 0 < len(content) <= 32 * 1024 * 1024:
        raise ValueError("The file changed after validation")
    return await client.upload(
        tenant,
        filename=file.name,
        content=content,
        workspace_id=workspace,
        project_id=project_id,
        parent_id=collection_id,
        mode="dataset",
    )


async def main() -> None:
    async with connect() as client:
        page = await client.document_versions(
            required("KOINON_TENANT_ID"),
            required("KOINON_DOCUMENT_ID"),
            page=1,
            page_size=25,
        )
        for version in page.items:
            print(version.source_version_id, version.sha256)


if __name__ == "__main__":
    asyncio.run(main())
