# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read an existing bounded result artifact; never execute SQL or create a public URL."""

import asyncio
from datetime import UTC, datetime
from hashlib import sha256
from inspect import isawaitable
from io import BytesIO
from uuid import UUID

from pyfly.container import Provider, service
from pyfly.core import Config
from pyfly.kernel import ConflictException, GoneException, PayloadTooLargeException, ResourceNotFoundException

from koinon.assistants.memory.egress import MemoryEgress
from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import ResultColumn, StoredResult
from koinon.evidence.ports import StoredResultPort
from koinon.evidence.settings import EvidenceSettings
from koinon.knowledge.adapters import NativeDomains, native_scope
from koinon.knowledge.service import KnowledgeFacade


@service(name="knowledge.stored_results")
class NativeStoredResults(StoredResultPort):
    def __init__(
        self,
        knowledge: KnowledgeFacade,
        domains: NativeDomains,
        config: Config,
        memory: Provider[MemoryEgress | None] | None = None,
    ):
        self.knowledge, self.domains, self.settings = knowledge, domains, config.bind(EvidenceSettings)
        self.memory = memory

    async def memory_check(self, subject, tenant_id, query_id):
        memory = self.memory.get() if self.memory else None
        if memory:
            await memory.query(subject, tenant_id, query_id)

    async def load(self, subject, tenant_id, dataset_id, query_id):
        from flyquery.core.services.query.query_repository import QueryRepository

        self.settings.validate()
        await self.memory_check(subject, tenant_id, query_id)
        chain = await self.knowledge._chain(subject, tenant_id, dataset_id)
        if chain[0].kind != "dataset":
            raise AccessDenied("Select an authorized dataset result", code="EVIDENCE_UNAVAILABLE")
        binding = await self.knowledge.binding(tenant_id, dataset_id, "structured", entry=chain[0])
        try:
            query_uuid, workspace_uuid = UUID(query_id), UUID(binding.native_workspace_id)
        except (ValueError, TypeError) as error:
            raise AccessDenied("This result is unavailable", code="EVIDENCE_UNAVAILABLE") from error
        with native_scope("structured", tenant_id, binding.native_workspace_id, subject):
            repository = self.domains._resolve(QueryRepository)
            arguments = {"tenant_id": tenant_id, "workspace_id": workspace_uuid}
            query = await repository.get_query(query_uuid, **arguments)
            record = await repository.get_result(query_uuid, **arguments)
            if (
                not query
                or not record
                or any(
                    str(value.get("tenant_id")) != tenant_id
                    or str(value.get("workspace_id")) != str(workspace_uuid)
                    for value in (query, record)
                )
                or (
                    str(query.get("dataset_id")) != binding.native_id
                    or query.get("execution_status") not in {"OK", "REFINED_OK"}
                )
            ):
                raise AccessDenied("This result is unavailable", code="EVIDENCE_UNAVAILABLE")
            expiry = record.get("ttl_expires_at")
            if not isinstance(expiry, datetime) or expiry.tzinfo is None:
                raise ConflictException(
                    "This historical result has no verified expiry", code="RESULT_EXPIRY_UNKNOWN"
                )
            if expiry <= datetime.now(UTC):
                raise GoneException(
                    "This stored result expired; it will not be rerun automatically", code="RESULT_EXPIRED"
                )
            key = record.get("result_object_key")
            if not key:
                if query.get("row_count") != 0:
                    raise ResourceNotFoundException(
                        "No stored result artifact exists", code="RESULT_ARTIFACT_UNAVAILABLE"
                    )
                await self.memory_check(subject, tenant_id, query_id)
                return self.empty(dataset_id, query_id, expiry), None
            expected = (
                f"flyquery/{tenant_id}/{workspace_uuid}/{binding.native_id}/results/{query_uuid}.parquet"
            )
            if key != expected:
                raise AccessDenied(
                    "This result has no admitted artifact binding", code="EVIDENCE_UNAVAILABLE"
                )
            size = record.get("result_byte_size")
            if type(size) is not int or not 0 < size <= self.settings.max_download_bytes:
                raise PayloadTooLargeException(
                    "Stored result exceeds the download limit", code="RESULT_TOO_LARGE"
                )
            store = self.domains.container.resolve_by_name("structured.object_store")
            async with asyncio.timeout(self.settings.download_timeout_seconds):
                head = await store.head(key)
                if head.size_bytes != size:
                    raise ConflictException(
                        "Stored result metadata changed", code="RESULT_INTEGRITY_MISMATCH"
                    )
                body = bytearray()
                stream = store.get(key)
                if isawaitable(stream):
                    stream = await stream
                try:
                    async for block in stream:
                        body.extend(block)
                        if len(body) > size:
                            raise ConflictException(
                                "Stored result bytes changed", code="RESULT_INTEGRITY_MISMATCH"
                            )
                finally:
                    close = getattr(stream, "aclose", None)
                    if close is not None:
                        await close()
            if len(body) != size:
                raise ConflictException("Stored result bytes changed", code="RESULT_INTEGRITY_MISMATCH")
        import pyarrow.parquet as pq

        try:
            parquet = pq.ParquetFile(BytesIO(body))
            rows = parquet.metadata.num_rows
            columns = tuple(
                ResultColumn(name=field.name, data_type=str(field.type)) for field in parquet.schema_arrow
            )
        except Exception as error:
            raise ConflictException(
                "Stored Parquet cannot be verified", code="RESULT_ARTIFACT_INVALID"
            ) from error
        if query.get("row_count") is not None and rows != query["row_count"]:
            raise ConflictException("Stored result row metadata changed", code="RESULT_INTEGRITY_MISMATCH")
        await self.knowledge._chain(subject, tenant_id, dataset_id)
        result = StoredResult(
            query_id=query_id,
            asset_id=dataset_id,
            revision=sha256(body).hexdigest(),
            row_count=rows,
            row_cap=None,
            truncated=None,
            completeness="unknown",
            byte_size=len(body),
            columns=columns,
            snapshot_ids=(),
            expires_at=expiry,
        )
        await self.memory_check(subject, tenant_id, query_id)
        return result, bytes(body)

    @staticmethod
    def empty(dataset_id, query_id, expiry):
        revision = sha256(
            (dataset_id + "\0" + query_id + "\0no-artifact\0" + expiry.isoformat()).encode()
        ).hexdigest()
        return StoredResult(
            query_id=query_id,
            asset_id=dataset_id,
            revision=revision,
            row_count=0,
            row_cap=None,
            truncated=None,
            completeness="unknown",
            byte_size=0,
            columns=(),
            snapshot_ids=(),
            expires_at=expiry,
        )

    async def describe(self, subject, tenant_id, dataset_id, query_id):
        result, _ = await self.load(subject, tenant_id, dataset_id, query_id)
        return result

    async def read(self, subject, tenant_id, result):
        current, content = await self.load(subject, tenant_id, result.asset_id, result.query_id)
        if current != result:
            raise ConflictException(
                "Review this changed result before exporting", code="RESULT_REVISION_CONFLICT"
            )
        if content is None:
            raise ResourceNotFoundException(
                "This empty execution stored no Parquet artifact or schema",
                code="RESULT_ARTIFACT_UNAVAILABLE",
            )
        for position in range(0, len(content), 1024 * 1024):
            await self.knowledge._chain(subject, tenant_id, result.asset_id)
            if current.expires_at <= datetime.now(UTC):
                raise GoneException("This stored result expired", code="RESULT_EXPIRED")
            await self.memory_check(subject, tenant_id, result.query_id)
            yield content[position : position + 1024 * 1024]
