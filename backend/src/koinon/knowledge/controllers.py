# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

from pyfly.container import rest_controller
from pyfly.kernel import InvalidRequestException, PayloadTooLargeException
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, post_mapping, request_mapping
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import Response

from koinon.knowledge.content import ContentUpdates
from koinon.knowledge.document_history.download_response import original_file_response
from koinon.knowledge.document_history.downloads import OriginalDownloads
from koinon.knowledge.dtos import (
    DocumentReingestInput,
    DocumentRevisionPreconditions,
    QueryInput,
    SearchInput,
    TableReingestInput,
)
from koinon.knowledge.service import KnowledgeFacade
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class KnowledgeController:
    def __init__(self, knowledge: KnowledgeFacade, downloads: OriginalDownloads):
        self.knowledge = knowledge
        self.downloads = downloads

    @post_mapping("/sources/upload", status_code=201)
    async def upload(self, tenant_id: PathVar[str], request: Request) -> dict:
        identity = identity_from_request(request)
        received = 0
        limit = self.knowledge.settings.max_upload_bytes

        async def bounded_receive():
            nonlocal received
            message = await request.receive()
            received += len(message.get("body", b""))
            if received > limit + 65536:
                raise PayloadTooLargeException(
                    "Multipart request exceeds the upload limit", code="UPLOAD_TOO_LARGE"
                )
            return message

        bounded = Request(request.scope, bounded_receive)
        async with bounded.form(max_files=1, max_fields=5, max_part_size=4096) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile) or set(form) - {
                "file",
                "workspace_id",
                "project_id",
                "parent_id",
                "mode",
            }:
                raise InvalidRequestException(
                    "Supply one file and its workspace/project/parent/mode", code="INVALID_UPLOAD"
                )
            fields = {name: form.get(name) for name in ("workspace_id", "project_id", "parent_id", "mode")}
            if any(not isinstance(value, str) or not value or len(value) > 64 for value in fields.values()):
                raise InvalidRequestException(
                    "Choose a complete catalog context and mode", code="INVALID_UPLOAD_CONTEXT"
                )
            await self.knowledge._chain(identity.subject, tenant_id, fields["parent_id"], "ingest:write")
            content = bytearray()
            while chunk := await file.read(65536):
                content.extend(chunk)
                if len(content) > limit:
                    raise PayloadTooLargeException(
                        "Uploaded file exceeds the byte limit", code="UPLOAD_TOO_LARGE"
                    )
            try:
                return await self.knowledge.upload(
                    identity.subject, tenant_id, filename=file.filename, content=bytes(content), **fields
                )
            except ValueError as error:
                raise InvalidRequestException(str(error), code="INVALID_UPLOAD") from error

    @post_mapping("/search")
    async def search(self, tenant_id: PathVar[str], body: Valid[Body[SearchInput]], request: Request) -> dict:
        return await self.knowledge.search(
            identity_from_request(request).subject, tenant_id, **body.model_dump()
        )

    @post_mapping("/query")
    async def query(self, tenant_id: PathVar[str], body: Valid[Body[QueryInput]], request: Request) -> dict:
        if not body.question.strip() and body.sql is None:
            raise InvalidRequestException("Supply a question or read-only SQL", code="EMPTY_QUERY")
        return await self.knowledge.query(
            identity_from_request(request).subject, tenant_id, **body.model_dump()
        )

    @get_mapping("/datasets/{dataset_id}/schema")
    async def schema(self, tenant_id: PathVar[str], dataset_id: PathVar[str], request: Request) -> dict:
        return await self.knowledge.schema(identity_from_request(request).subject, tenant_id, dataset_id)

    @get_mapping("/lineage")
    async def lineage(
        self, tenant_id: PathVar[str], request: Request, asset_id: QueryParam[str | None] = None
    ) -> dict:
        return await self.knowledge.lineage(identity_from_request(request).subject, tenant_id, asset_id)

    @get_mapping("/documents/{document_id}/chunks")
    async def document_chunks(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        request: Request,
        offset: QueryParam[int] = 0,
        limit: QueryParam[int] = 50,
        page: QueryParam[int | None] = None,
        section: QueryParam[str | None] = None,
        q: QueryParam[str | None] = None,
    ) -> dict:
        return await self.knowledge.document_chunks(
            identity_from_request(request).subject,
            tenant_id,
            document_id,
            offset=offset,
            limit=limit,
            page=page,
            section=section,
            q=q,
        )

    @get_mapping("/documents/{document_id}/original")
    async def document_original(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        request: Request,
    ) -> Response:
        download = await self.downloads.open(
            identity_from_request(request).subject,
            tenant_id,
            document_id,
            context=request.state.security_context,
        )
        return await original_file_response(download)


@rest_controller(name="knowledge.content_controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class ContentController:
    def __init__(self, content: ContentUpdates, knowledge: KnowledgeFacade):
        self.content, self.knowledge = content, knowledge

    async def _file(self, request):
        received = 0
        limit = self.knowledge.settings.max_upload_bytes

        async def bounded_receive():
            nonlocal received
            message = await request.receive()
            received += len(message.get("body", b""))
            if received > limit + 65536:
                raise PayloadTooLargeException(
                    "Multipart request exceeds the upload limit", code="UPLOAD_TOO_LARGE"
                )
            return message

        bounded = Request(request.scope, bounded_receive)
        async with bounded.form(max_files=1, max_fields=1, max_part_size=4096) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile) or set(form) - {"file", "acknowledge_chunk_invalidation"}:
                raise InvalidRequestException("Supply one replacement file", code="INVALID_UPLOAD")
            content = bytearray()
            while chunk := await file.read(65536):
                content.extend(chunk)
                if len(content) > limit:
                    raise PayloadTooLargeException(
                        "Uploaded file exceeds the byte limit", code="UPLOAD_TOO_LARGE"
                    )
            try:
                self.knowledge._validate_file(file.filename, content)
            except ValueError as error:
                raise InvalidRequestException(str(error), code="INVALID_UPLOAD") from error
            return file.filename, bytes(content), form.get("acknowledge_chunk_invalidation") == "true"

    @post_mapping("/documents/{document_id}/reingest", status_code=201)
    async def reingest_document(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        body: Valid[Body[DocumentReingestInput]],
        request: Request,
    ) -> dict:
        return await self.content.reingest_document(
            identity_from_request(request).subject,
            tenant_id,
            document_id,
            expected_sha256=request.headers.get("if-match", "").strip('"'),
            acknowledge_chunk_invalidation=body.acknowledge_chunk_invalidation,
            **DocumentRevisionPreconditions.model_validate(
                {
                    "expected_source_version_id": request.headers.get("x-koinon-source-version"),
                    "expected_extraction_id": request.headers.get("x-koinon-extraction"),
                }
            ).model_dump(mode="json"),
        )

    @post_mapping("/datasets/{dataset_id}/tables/{table_id}/reingest", status_code=201)
    async def reingest_table(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        body: Valid[Body[TableReingestInput]],
        request: Request,
    ) -> dict:
        return await self.content.reingest_table(
            identity_from_request(request).subject,
            tenant_id,
            dataset_id,
            table_id,
            expected_snapshot_id=request.headers.get("if-match", "").strip('"'),
        )

    @post_mapping("/documents/{document_id}/content", status_code=201)
    async def document(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        request: Request,
    ) -> dict:
        subject = identity_from_request(request).subject
        await self.content._writable(subject, tenant_id, document_id)
        filename, content, acknowledgment = await self._file(request)
        return await self.content.document(
            subject,
            tenant_id,
            document_id,
            filename=filename,
            content=content,
            expected_sha256=request.headers.get("if-match", "").strip('"'),
            acknowledge_chunk_invalidation=acknowledgment,
            **DocumentRevisionPreconditions.model_validate(
                {
                    "expected_source_version_id": request.headers.get("x-koinon-source-version"),
                    "expected_extraction_id": request.headers.get("x-koinon-extraction"),
                }
            ).model_dump(mode="json"),
        )

    @post_mapping("/datasets/{dataset_id}/tables/{table_id}/content", status_code=201)
    async def table(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        request: Request,
    ) -> dict:
        subject = identity_from_request(request).subject
        await self.content._writable(subject, tenant_id, table_id)
        filename, content, _ = await self._file(request)
        return await self.content.table(
            subject,
            tenant_id,
            dataset_id,
            table_id,
            filename=filename,
            content=content,
            expected_snapshot_id=request.headers.get("if-match", "").strip('"'),
        )
