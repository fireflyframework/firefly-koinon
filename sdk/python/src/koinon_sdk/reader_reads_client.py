# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed private reads carry source choice in the request body."""

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import quote

from koinon_sdk.contracts import BinaryDownload
from koinon_sdk.coordinates import TableColumnBindingPage, TableCoordinateManifest, TableRowRangePage
from koinon_sdk.curated import KnowledgeItemView
from koinon_sdk.document_history import (
    DocumentExtractionPage,
    DocumentPartContent,
    DocumentPartPage,
    DocumentVersion,
    DocumentVersionPage,
)
from koinon_sdk.document_reads import DocumentChunksReadInput, DocumentPartsReadInput, LineageReadInput
from koinon_sdk.exports import Export
from koinon_sdk.models import CatalogEntry, ChatThread, DatasetSchema, DocumentChunks, Lineage
from koinon_sdk.provenance import TableProvenance
from koinon_sdk.provenance_reads import (
    SnapshotHistoryReadInput,
    SnapshotPageReadInput,
    SnapshotReadInput,
    TableSnapshotReadPage,
)
from koinon_sdk.reader_sources import ReaderPageInput, ReaderReadInput
from koinon_sdk.sharing import SharedConversation


class ReaderReadsMixin(ABC):
    @staticmethod
    @abstractmethod
    def _tenant(tenant_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def _download(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        if_none_match: str | None = None,
        method: str = "GET",
        json: Any = None,
    ) -> BinaryDownload:
        raise NotImplementedError

    async def read_catalog_entry(self, tenant_id: str, entry_id: str, value: ReaderReadInput) -> CatalogEntry:
        return CatalogEntry.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "catalog"
                + "/"
                + quote(str(entry_id), safe="")
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_dataset_schema(
        self, tenant_id: str, dataset_id: str, value: ReaderReadInput
    ) -> DatasetSchema:
        return DatasetSchema.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "datasets"
                + "/"
                + quote(str(dataset_id), safe="")
                + "/"
                + "schema"
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_lineage(self, tenant_id: str, value: LineageReadInput) -> Lineage:
        return Lineage.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/" + "lineage" + "/" + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_document_chunks(
        self, tenant_id: str, document_id: str, value: DocumentChunksReadInput
    ) -> DocumentChunks:
        return DocumentChunks.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "documents"
                + "/"
                + quote(str(document_id), safe="")
                + "/"
                + "chunks"
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_document_original(
        self, tenant_id: str, document_id: str, value: ReaderReadInput
    ) -> BinaryDownload:
        return await self._download(
            self._tenant(tenant_id)
            + "/"
            + "documents"
            + "/"
            + quote(str(document_id), safe="")
            + "/"
            + "original"
            + "/"
            + "read",
            method="POST",
            json=value.model_dump(mode="json", exclude_unset=True),
        )

    async def read_document_versions(
        self, tenant_id: str, document_id: str, value: ReaderPageInput
    ) -> DocumentVersionPage:
        return DocumentVersionPage.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "documents"
                + "/"
                + quote(str(document_id), safe="")
                + "/"
                + "versions"
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_document_version(
        self, tenant_id: str, document_id: str, source_version_id: str, value: ReaderReadInput
    ) -> DocumentVersion:
        return DocumentVersion.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "documents"
                + "/"
                + quote(str(document_id), safe="")
                + "/"
                + "versions"
                + "/"
                + quote(str(source_version_id), safe="")
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_document_extractions(
        self, tenant_id: str, document_id: str, source_version_id: str, value: ReaderPageInput
    ) -> DocumentExtractionPage:
        return DocumentExtractionPage.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "documents"
                + "/"
                + quote(str(document_id), safe="")
                + "/"
                + "versions"
                + "/"
                + quote(str(source_version_id), safe="")
                + "/"
                + "extractions"
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_document_parts(
        self,
        tenant_id: str,
        document_id: str,
        source_version_id: str,
        extraction_id: str,
        value: DocumentPartsReadInput,
    ) -> DocumentPartPage:
        return DocumentPartPage.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "documents"
                + "/"
                + quote(str(document_id), safe="")
                + "/"
                + "versions"
                + "/"
                + quote(str(source_version_id), safe="")
                + "/"
                + "extractions"
                + "/"
                + quote(str(extraction_id), safe="")
                + "/"
                + "parts"
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_document_part(
        self,
        tenant_id: str,
        document_id: str,
        source_version_id: str,
        extraction_id: str,
        source_part_id: str,
        value: ReaderReadInput,
    ) -> DocumentPartContent:
        return DocumentPartContent.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "documents"
                + "/"
                + quote(str(document_id), safe="")
                + "/"
                + "versions"
                + "/"
                + quote(str(source_version_id), safe="")
                + "/"
                + "extractions"
                + "/"
                + quote(str(extraction_id), safe="")
                + "/"
                + "parts"
                + "/"
                + quote(str(source_part_id), safe="")
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_document_version_original(
        self, tenant_id: str, document_id: str, source_version_id: str, value: ReaderReadInput
    ) -> BinaryDownload:
        return await self._download(
            self._tenant(tenant_id)
            + "/"
            + "documents"
            + "/"
            + quote(str(document_id), safe="")
            + "/"
            + "versions"
            + "/"
            + quote(str(source_version_id), safe="")
            + "/"
            + "original"
            + "/"
            + "read",
            method="POST",
            json=value.model_dump(mode="json", exclude_unset=True),
        )

    async def read_table_provenance(
        self, tenant_id: str, dataset_id: str, table_id: str, value: SnapshotReadInput
    ) -> TableProvenance:
        return TableProvenance.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "datasets"
                + "/"
                + quote(str(dataset_id), safe="")
                + "/"
                + "tables"
                + "/"
                + quote(str(table_id), safe="")
                + "/"
                + "provenance"
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_table_snapshots(
        self, tenant_id: str, dataset_id: str, table_id: str, value: SnapshotHistoryReadInput
    ) -> TableSnapshotReadPage:
        return TableSnapshotReadPage.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "datasets"
                + "/"
                + quote(str(dataset_id), safe="")
                + "/"
                + "tables"
                + "/"
                + quote(str(table_id), safe="")
                + "/"
                + "snapshots"
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_table_coordinates(
        self, tenant_id: str, dataset_id: str, table_id: str, value: SnapshotReadInput
    ) -> TableCoordinateManifest:
        return TableCoordinateManifest.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "datasets"
                + "/"
                + quote(str(dataset_id), safe="")
                + "/"
                + "tables"
                + "/"
                + quote(str(table_id), safe="")
                + "/"
                + "coordinates"
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_table_coordinate_rows(
        self, tenant_id: str, dataset_id: str, table_id: str, value: SnapshotPageReadInput
    ) -> TableRowRangePage:
        return TableRowRangePage.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "datasets"
                + "/"
                + quote(str(dataset_id), safe="")
                + "/"
                + "tables"
                + "/"
                + quote(str(table_id), safe="")
                + "/"
                + "coordinates"
                + "/"
                + "rows"
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_table_coordinate_columns(
        self, tenant_id: str, dataset_id: str, table_id: str, value: SnapshotPageReadInput
    ) -> TableColumnBindingPage:
        return TableColumnBindingPage.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "datasets"
                + "/"
                + quote(str(dataset_id), safe="")
                + "/"
                + "tables"
                + "/"
                + quote(str(table_id), safe="")
                + "/"
                + "coordinates"
                + "/"
                + "columns"
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_knowledge_item(
        self, tenant_id: str, item_id: str, value: ReaderReadInput
    ) -> KnowledgeItemView:
        return KnowledgeItemView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "knowledge-items"
                + "/"
                + quote(str(item_id), safe="")
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_knowledge_version(
        self, tenant_id: str, item_id: str, version: int, value: ReaderReadInput
    ) -> KnowledgeItemView:
        return KnowledgeItemView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "knowledge-items"
                + "/"
                + quote(str(item_id), safe="")
                + "/"
                + "versions"
                + "/"
                + quote(str(version), safe="")
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_export(self, tenant_id: str, export_id: str, value: ReaderReadInput) -> Export:
        return Export.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "exports"
                + "/"
                + quote(str(export_id), safe="")
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_export_download(
        self, tenant_id: str, export_id: str, value: ReaderReadInput
    ) -> BinaryDownload:
        return await self._download(
            self._tenant(tenant_id)
            + "/"
            + "exports"
            + "/"
            + quote(str(export_id), safe="")
            + "/"
            + "download"
            + "/"
            + "read",
            method="POST",
            json=value.model_dump(mode="json", exclude_unset=True),
        )

    async def read_share(self, tenant_id: str, share_id: str, value: ReaderReadInput) -> SharedConversation:
        return SharedConversation.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/" + "shares" + "/" + quote(str(share_id), safe="") + "/" + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )

    async def read_thread(self, tenant_id: str, thread_id: str, value: ReaderReadInput) -> ChatThread:
        return ChatThread.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id)
                + "/"
                + "chat"
                + "/"
                + "threads"
                + "/"
                + quote(str(thread_id), safe="")
                + "/"
                + "read",
                json=value.model_dump(mode="json", exclude_unset=True),
            )
        )
