# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist actual whole-document reads over committed normalized full sections."""

import inspect
import json
from collections.abc import Awaitable, Callable
from hashlib import sha256
from typing import NoReturn
from uuid import NAMESPACE_URL, uuid4, uuid5

from pyfly.kernel import DataIntegrityException, ResourceNotFoundException, ServiceUnavailableException

from flycanon.core.services.sources.lineage.capture import artifact
from flycanon.core.services.sources.lineage.dtos import (
    DocumentReadPin,
    DocumentScope,
    ExtractedPage,
    WholeDocumentPart,
    WholeDocumentRead,
)
from flycanon.core.services.sources.lineage.ports import LineageQuery
from flycanon.core.services.sources.lineage.service import DocumentLineage, identity


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def joined_view(pages) -> bytes:
    return "\n".join(page["text"] for page in pages).encode()


def grouped_sections(sections):
    pages, positions = [], {}
    for section in sections:
        if not section["text"].strip():
            continue
        page = section["page"]
        if page is not None and page in positions:
            target = pages[positions[page]]
            target["text"] += "\n" + section["text"]
            target["section_ids"].append(section["id"])
            target["section_digests"].append(section["sha256"])
        else:
            if page is not None:
                positions[page] = len(pages)
            pages.append(
                {
                    "text": section["text"],
                    "page": page,
                    "section_ids": [section["id"]],
                    "section_digests": [section["sha256"]],
                }
            )
    return pages


class WholeDocumentReader:
    def __init__(
        self, lineage: DocumentLineage, *, max_bytes: int = 64 * 1024 * 1024, max_parts: int = 100000
    ):
        self.lineage = lineage
        self.max_bytes = max_bytes
        self.max_parts = max_parts

    async def resolve_parts(
        self,
        scope: DocumentScope,
        *,
        source_id: str,
        source_version_id: str,
        extraction_id: str,
        part_ids: tuple[str, ...],
    ) -> tuple[WholeDocumentPart, ...]:
        from flycanon.core.services.sources.lineage.exact_parts import read_exact_parts

        await self.lineage.require_schema()
        async with self.lineage.repository.read() as session:
            purpose = await session.scalar(
                LineageQuery(
                    "extraction",
                    scope,
                    source_id=source_id,
                    equal={"id": extraction_id, "version_id": source_version_id},
                ),
                "purpose",
            )
        if purpose == "ingestion":
            from flycanon.core.services.sources.lineage.ingestion_parts import (
                read_exact_ingestion_chunk_parts,
            )

            return await read_exact_ingestion_chunk_parts(
                self,
                scope,
                source_id=source_id,
                source_version_id=source_version_id,
                extraction_id=extraction_id,
                part_ids=part_ids,
            )
        return await read_exact_parts(
            self,
            scope,
            source_id=source_id,
            source_version_id=source_version_id,
            extraction_id=extraction_id,
            part_ids=part_ids,
        )

    async def pin(self, scope: DocumentScope, source_id: str) -> DocumentReadPin:
        await self.lineage.require_schema()
        head = await self.lineage.head(scope, source_id)
        if head is None or not head["version_id"] or not head["extraction_id"]:
            self._unavailable(
                "This document needs an explicitly authorized versioned intake before whole-document answers"
            )
        version = await self.lineage.version(scope, source_id, head["version_id"])
        async with self.lineage.repository.read() as session:
            extraction = await session.first(
                LineageQuery(
                    "extraction",
                    scope,
                    source_id=source_id,
                    equal={"id": head["extraction_id"], "version_id": version["id"], "purpose": "ingestion"},
                )
            )
            if extraction is None:
                self._unavailable("The exact committed document extraction is unavailable")
            normalized = await session.one(
                LineageQuery(
                    "artifact", scope, source_id=source_id, equal={"id": extraction["normalized_artifact_id"]}
                )
            )
        return DocumentReadPin(
            source_id,
            version["id"],
            extraction["id"],
            version["filename"],
            extraction["projection"]["kind"],
            version["sha256"],
            version["bytes"],
            normalized["sha256"],
        )

    async def read(
        self,
        scope: DocumentScope,
        *,
        source_id: str,
        source_version_id: str,
        ingestion_extraction_id: str,
        authorize: Callable[[], Awaitable[None]] | None = None,
    ) -> WholeDocumentRead:
        if authorize is not None:
            await authorize()
        await self.lineage.require_schema()
        async with self.lineage.repository.read() as session:
            ingestion = await session.first(
                LineageQuery(
                    "extraction",
                    scope,
                    source_id=source_id,
                    equal={
                        "id": ingestion_extraction_id,
                        "version_id": source_version_id,
                        "purpose": "ingestion",
                    },
                )
            )
            if ingestion is None:
                raise ResourceNotFoundException(
                    "The exact committed document extraction is unavailable",
                    code="DOCUMENT_EXTRACTION_REQUIRED",
                )
            input_artifact = await session.one(
                LineageQuery(
                    "artifact", scope, source_id=source_id, equal={"id": ingestion["normalized_artifact_id"]}
                )
            )
            sections = await session.all(
                LineageQuery(
                    "part",
                    scope,
                    source_id=source_id,
                    order=("ordinal", "id"),
                    limit=self.max_parts + 1,
                    equal={"extraction_id": ingestion_extraction_id, "kind": "section"},
                )
            )
        version = await self.lineage.version(scope, source_id, source_version_id)
        if version["bytes"] > self.max_bytes or input_artifact["bytes"] > self.max_bytes:
            self._unavailable("The full document exceeds the verified read limit")
        await self.lineage.original(scope, source_id, source_version_id, max_bytes=self.max_bytes)
        await self.lineage._verified(input_artifact, self.max_bytes)
        if not sections or len(sections) > self.max_parts:
            self._unavailable("Complete committed document sections are required")
        if input_artifact["role"] != "normalized":
            self._unavailable("The committed normalized input binding is unavailable")
        if any(section["artifact_id"] != input_artifact["id"] for section in sections):
            self._unavailable("Document sections have an incompatible input binding")
        if any(sha256(section["text"].encode()).hexdigest() != section["sha256"] for section in sections):
            self._unavailable("Committed document sections failed integrity verification")
        if sum(len(section["text"].encode()) for section in sections) > self.max_bytes:
            self._unavailable("The complete extracted text exceeds the verified read limit")
        pages = grouped_sections(sections)
        if not pages:
            self._unavailable("The committed document has no readable full sections")
        reader_sha = sha256(
            (inspect.getsource(grouped_sections) + inspect.getsource(joined_view)).encode()
        ).hexdigest()
        signature = sha256(
            canonical(
                {
                    "scope": [scope.tenant_id, scope.workspace_id, source_id],
                    "source_version_id": source_version_id,
                    "input_extraction_id": ingestion_extraction_id,
                    "raw_sha256": version["sha256"],
                    "input_sha256": input_artifact["sha256"],
                    "reader": reader_sha,
                    "pages": pages,
                }
            )
        ).hexdigest()
        extraction_id = str(uuid5(NAMESPACE_URL, "koinon.document.whole-read.v1:" + signature))
        if authorize is not None:
            await authorize()
        result = await self._existing(
            scope,
            source_id,
            extraction_id,
            ingestion_extraction_id,
            version,
            input_artifact,
            signature,
            pages,
        )
        if result is not None:
            if authorize is not None:
                await authorize()
            return result
        view = joined_view(pages)
        if len(view) > self.max_bytes:
            self._unavailable("The exact whole-document view exceeds the verified read limit")
        try:
            output = await artifact(
                self.lineage, scope, source_id, view, "whole_document_view", "text/plain; charset=utf-8"
            )
        except Exception as error:
            raise ServiceUnavailableException(
                "The complete document view could not be persisted", code="DOCUMENT_EXTRACTION_UNAVAILABLE"
            ) from error
        if output["bytes"] > self.max_bytes:
            self._unavailable("The exact page manifest exceeds the verified read limit")
        base = identity(scope, source_id)
        part_rows = [
            {
                "id": str(uuid4()),
                **base,
                "extraction_id": extraction_id,
                "artifact_id": output["id"],
                "kind": "page",
                "parent_id": page["section_ids"][0] if len(page["section_ids"]) == 1 else None,
                "ordinal": index,
                "text": page["text"],
                "sha256": sha256(page["text"].encode()).hexdigest(),
                "page": page["page"],
                "section_path": None,
                "char_start": None,
                "char_end": None,
                "offset_basis": "extracted_page_sequence",
                "projection_chunk_id": None,
            }
            for index, page in enumerate(pages)
        ]
        try:
            async with self.lineage.repository.write() as session:
                if authorize is not None:
                    await authorize()
                await session.insert("artifact", dict(**output))
                await session.insert(
                    "extraction",
                    dict(
                        id=extraction_id,
                        **base,
                        version_id=source_version_id,
                        purpose="whole_document_read",
                        normalized_artifact_id=input_artifact["id"],
                        predecessor_id=None,
                        implementation={
                            "stage": "regroup_committed_sections",
                            "implementation_sha256": reader_sha,
                            "reader_signature": signature,
                            "input_loader": ingestion["implementation"].get("loader"),
                        },
                        coverage="file_section",
                        projection={
                            "input_extraction_id": ingestion_extraction_id,
                            "output_artifact_id": output["id"],
                            "page_basis": "recorded_loader",
                            "view_representation": "utf8_pages_joined_newline.v1",
                            "section_ids_by_page": [page["section_ids"] for page in pages],
                            "source_section_digests": {
                                section["id"]: section["sha256"] for section in sections
                            },
                        },
                    ),
                )
                await session.insert("part", part_rows)
                await session.insert(
                    "step",
                    dict(
                        id=str(uuid4()),
                        **base,
                        extraction_id=extraction_id,
                        ordinal=0,
                        stage="regroup_committed_sections",
                        input_artifact_id=input_artifact["id"],
                        output_artifact_id=output["id"],
                        implementation={"implementation_sha256": reader_sha},
                        parameters={
                            "input_extraction_id": ingestion_extraction_id,
                            "section_ids_by_page": [page["section_ids"] for page in pages],
                            "loader_rerun": False,
                        },
                    ),
                )
                await session.insert(
                    "event",
                    dict(
                        id=str(uuid4()),
                        **base,
                        version_id=source_version_id,
                        extraction_id=extraction_id,
                        status="committed",
                    ),
                )
        except DataIntegrityException:
            reused = await self._existing(
                scope,
                source_id,
                extraction_id,
                ingestion_extraction_id,
                version,
                input_artifact,
                signature,
                pages,
            )
            if reused is None:
                raise
            if authorize is not None:
                await authorize()
            return reused
        if authorize is not None:
            await authorize()
        return self._result(
            source_id,
            extraction_id,
            ingestion_extraction_id,
            version,
            input_artifact,
            output,
            part_rows,
            pages,
            {section["id"]: section["sha256"] for section in sections},
        )

    async def _existing(
        self, scope, source_id, extraction_id, ingestion_id, version, normalized, signature, pages
    ):
        async with self.lineage.repository.read() as session:
            record = await session.first(
                LineageQuery(
                    "extraction",
                    scope,
                    source_id=source_id,
                    equal={
                        "id": extraction_id,
                        "version_id": version["id"],
                        "purpose": "whole_document_read",
                    },
                )
            )
            if record is None:
                return None
            projection = record["projection"]
            if (
                record["normalized_artifact_id"] != normalized["id"]
                or record["implementation"].get("reader_signature") != signature
                or projection.get("input_extraction_id") != ingestion_id
                or projection.get("page_basis") != "recorded_loader"
                or projection.get("view_representation") != "utf8_pages_joined_newline.v1"
                or projection.get("section_ids_by_page") != [page["section_ids"] for page in pages]
            ):
                self._unavailable("The stored whole-document view has an incompatible input binding")
            output = await session.first(
                LineageQuery(
                    "artifact", scope, source_id=source_id, equal={"id": projection.get("output_artifact_id")}
                )
            )
            rows = await session.all(
                LineageQuery(
                    "part",
                    scope,
                    source_id=source_id,
                    order=("ordinal",),
                    limit=self.max_parts + 1,
                    equal={"extraction_id": extraction_id, "kind": "page"},
                )
            )
        if output is None or output["bytes"] > self.max_bytes or len(rows) != len(pages):
            self._unavailable("The complete recorded whole-document view is unavailable")
        digests = projection.get("source_section_digests", {})
        if any(
            digests.get(identifier) != digest
            for page in pages
            for identifier, digest in zip(page["section_ids"], page["section_digests"], strict=True)
        ):
            self._unavailable("The recorded parent section digests are incompatible")
        expected_view = joined_view(pages)
        if await self.lineage._verified(output, self.max_bytes) != expected_view:
            self._unavailable("The recorded whole-document view failed integrity verification")
        for index, (row, page) in enumerate(zip(rows, pages, strict=True)):
            if (
                row["ordinal"] != index
                or row["artifact_id"] != output["id"]
                or row["text"] != page["text"]
                or row["page"] != page["page"]
                or row["sha256"] != sha256(page["text"].encode()).hexdigest()
            ):
                self._unavailable("The recorded page manifest failed integrity verification")
        return self._result(
            source_id,
            extraction_id,
            ingestion_id,
            version,
            normalized,
            output,
            rows,
            pages,
            projection.get("source_section_digests", {}),
        )

    @staticmethod
    def _result(source_id, extraction_id, ingestion_id, version, normalized, output, rows, pages, digests):
        return WholeDocumentRead(
            source_id,
            version["id"],
            extraction_id,
            ingestion_id,
            output["id"],
            output["sha256"],
            normalized["id"],
            normalized["sha256"],
            version["sha256"],
            tuple(
                ExtractedPage(
                    row["id"],
                    row["text"],
                    row["sha256"],
                    row["page"],
                    "recorded_loader",
                    tuple((identifier, digests[identifier]) for identifier in page["section_ids"]),
                )
                for row, page in zip(rows, pages, strict=True)
            ),
        )

    @staticmethod
    def _unavailable(message) -> NoReturn:
        raise ServiceUnavailableException(message, code="DOCUMENT_EXTRACTION_UNAVAILABLE")
