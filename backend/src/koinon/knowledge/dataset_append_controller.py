# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.kernel import InvalidRequestException, PayloadTooLargeException
from pyfly.web import PathVar, post_mapping, request_mapping
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.evidence.http import private_json
from koinon.knowledge.dataset_append import DatasetFiles
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.dataset_files_controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class DatasetFilesController:
    def __init__(self, files: DatasetFiles):
        self.files = files

    @post_mapping("/datasets/{dataset_id}/files", status_code=201)
    async def append(
        self, tenant_id: PathVar[str], dataset_id: PathVar[str], request: Request
    ) -> JSONResponse:
        subject = identity_from_request(request).subject
        await self.files.scope(subject, tenant_id, dataset_id)
        received = 0
        limit = self.files.knowledge.settings.max_upload_bytes

        async def bounded_receive():
            nonlocal received
            message = await request.receive()
            received += len(message.get("body", b""))
            if received > limit + 65536:
                raise PayloadTooLargeException(
                    "Multipart upload exceeds the byte limit", code="UPLOAD_TOO_LARGE"
                )
            return message

        bounded = Request(request.scope, bounded_receive)
        async with bounded.form(max_files=1, max_fields=0, max_part_size=4096) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile) or set(form) != {"file"} or len(form.getlist("file")) != 1:
                raise InvalidRequestException("Supply one file for this dataset", code="INVALID_UPLOAD")
            content = bytearray()
            while chunk := await file.read(65536):
                content.extend(chunk)
                if len(content) > limit:
                    raise PayloadTooLargeException(
                        "Uploaded file exceeds the byte limit", code="UPLOAD_TOO_LARGE"
                    )
            try:
                result = await self.files.append(
                    subject,
                    tenant_id,
                    dataset_id,
                    filename=file.filename,
                    content=bytes(content),
                    idempotency_key=request.headers.get("Idempotency-Key", ""),
                )
            except ValueError as error:
                raise InvalidRequestException(str(error), code="INVALID_UPLOAD") from error
        return private_json(result, status=201)
