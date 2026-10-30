# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Authorize the current canonical document around each exact historical read."""

from pydantic import ValidationError
from pyfly.container import service
from pyfly.kernel import ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.document_history.dtos import (
    DocumentExtractionPage,
    DocumentPartContent,
    DocumentPartPage,
    DocumentVersion,
    DocumentVersionPage,
)
from koinon.knowledge.document_history.native import NativeDocumentHistory, pagination
from koinon.knowledge.service import KnowledgeFacade


@service
class DocumentHistoryService:
    def __init__(self, knowledge: KnowledgeFacade, history: NativeDocumentHistory):
        self.knowledge, self.history = knowledge, history

    @staticmethod
    def _binding(chain, binding):
        return chain[1].id, binding.native_workspace_id, binding.native_id

    async def _read(self, operation, subject, tenant_id, document_id, **arguments):
        chain, binding = await self.knowledge._document(subject, tenant_id, document_id)
        before = self._binding(chain, binding)
        result = await getattr(self.history, operation)(
            actor=subject,
            tenant_id=tenant_id,
            workspace_id=binding.native_workspace_id,
            source_id=binding.native_id,
            **arguments,
        )
        current_chain, current_binding = await self.knowledge._document(subject, tenant_id, document_id)
        if self._binding(current_chain, current_binding) != before:
            raise AccessDenied("The document binding changed during the read", code="DOCUMENT_SCOPE_MISMATCH")
        identity = dict(document_id=document_id, catalog_source_id=before[0], native_source_id=before[2])
        return result, identity

    @staticmethod
    def _typed(model, values):
        try:
            return model.model_validate(values)
        except ValidationError as error:
            raise ServiceUnavailableException(
                "The recorded document history is incomplete", code="DOCUMENT_HISTORY_INVALID"
            ) from error

    async def versions(self, subject, tenant_id, document_id, *, page=1, page_size=25):
        pagination(page, page_size)
        result, identity = await self._read(
            "versions",
            subject,
            tenant_id,
            document_id,
            page=page,
            page_size=page_size,
        )
        return self._typed(
            DocumentVersionPage,
            {
                **result,
                "items": tuple({**row, **identity} for row in result["items"]),
            },
        )

    async def version(self, subject, tenant_id, document_id, source_version_id):
        result, identity = await self._read(
            "version",
            subject,
            tenant_id,
            document_id,
            source_version_id=source_version_id,
        )
        self._exact(result, source_version_id)
        return self._typed(DocumentVersion, {**result, **identity})

    @staticmethod
    def _exact(row, version, extraction=None, part=None):
        if (
            row.get("source_version_id") != version
            or extraction is not None
            and row.get("extraction_id") != extraction
            or part is not None
            and row.get("source_part_id") != part
        ):
            raise AccessDenied("The exact document identity is unavailable", code="DOCUMENT_SCOPE_MISMATCH")

    async def extractions(self, subject, tenant_id, document_id, source_version_id, *, page=1, page_size=25):
        pagination(page, page_size)
        result, identity = await self._read(
            "extractions",
            subject,
            tenant_id,
            document_id,
            source_version_id=source_version_id,
            page=page,
            page_size=page_size,
        )
        for row in result["items"]:
            self._exact(row, source_version_id)
        return self._typed(
            DocumentExtractionPage,
            {
                **result,
                "items": tuple({**row, **identity} for row in result["items"]),
            },
        )

    async def parts(
        self,
        subject,
        tenant_id,
        document_id,
        source_version_id,
        extraction_id,
        *,
        kind=None,
        page=1,
        page_size=25,
    ):
        pagination(page, page_size)
        result, identity = await self._read(
            "parts",
            subject,
            tenant_id,
            document_id,
            source_version_id=source_version_id,
            extraction_id=extraction_id,
            kind=kind,
            page=page,
            page_size=page_size,
        )
        for row in result["items"]:
            self._exact(row, source_version_id, extraction_id)
        return self._typed(
            DocumentPartPage,
            {
                **result,
                "items": tuple({**row, **identity} for row in result["items"]),
            },
        )

    async def part(self, subject, tenant_id, document_id, source_version_id, extraction_id, source_part_id):
        result, identity = await self._read(
            "part",
            subject,
            tenant_id,
            document_id,
            source_version_id=source_version_id,
            extraction_id=extraction_id,
            source_part_id=source_part_id,
        )
        self._exact(result, source_version_id, extraction_id, source_part_id)
        return self._typed(DocumentPartContent, {**result, **identity})

    async def original(self, subject, tenant_id, document_id, source_version_id):
        result, _ = await self._read(
            "original",
            subject,
            tenant_id,
            document_id,
            source_version_id=source_version_id,
            max_bytes=self.knowledge.settings.max_upload_bytes,
        )
        if result.version_id != source_version_id:
            raise AccessDenied("The historical original is unavailable", code="DOCUMENT_SCOPE_MISMATCH")
        return result
