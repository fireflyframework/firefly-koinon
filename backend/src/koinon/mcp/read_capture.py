# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Capture one real native read without replaying queries or accepting client source manifests."""

from hashlib import sha256

from mcp.server.mcpserver.exceptions import ToolError
from pyfly.context import ApplicationContext

from koinon.catalog.mappers import entry_dto
from koinon.catalog.service import CatalogService
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_context import reader_source_scope
from koinon.integrations.content_sources.read_service import SourceReader
from koinon.knowledge.capture_dtos import CapturedEvidence, DocumentRead, NativeCaptureLimits
from koinon.knowledge.curated.reads import CuratedKnowledgeReads
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence, document_reference
from koinon.knowledge.external_reviews.read_receipts import ExternalReadReceipts, not_recorded
from koinon.mcp.private_reviews import authenticated_operation


def native_read_capture(context: ApplicationContext):
    async def capture(raw: str, tenant_id: str, operation: str, arguments: dict):
        values = dict(arguments)
        choices = values.pop("reader_source_connections", None)

        async def execute(principal):
            native = context.get_bean(NativeKnowledgeEvidence)
            limits = NativeCaptureLimits(sources=64, receipt_bytes=262144)
            if operation == "search":
                observed = await native.search(principal, tenant_id, _limits=limits, **values)
            elif operation == "query":
                observed = await native.query(principal, tenant_id, _limits=limits, **values)
            elif operation == "schema":
                observed = await native.schema(principal, tenant_id, _limits=limits, **values)
                return {
                    **observed.data,
                    "read_receipt": not_recorded("incomplete_or_unsupported_source_manifest"),
                }
            elif operation == "catalog":
                row = await context.get_bean(CatalogService).get(principal, tenant_id, values["source_id"])
                return {**entry_dto(row), "read_receipt": not_recorded("catalog_is_not_source_evidence")}
            elif operation == "curated":
                data = await context.get_bean(CuratedKnowledgeReads).version(
                    principal, tenant_id, values["source_id"], values.get("version")
                )
                return {
                    **data.model_dump(mode="json"),
                    "read_receipt": not_recorded("transitive_lineage_unqualified"),
                }
            elif operation == "fetch" and arguments.get("kind") == "document":
                document_id = arguments["source_id"]
                data = await native.knowledge.document_chunks(
                    principal, tenant_id, document_id, offset=arguments["offset"], limit=arguments["limit"]
                )
                chain, binding = await native.entry(principal, tenant_id, document_id, "document")
                references = []
                for chunk in data["items"]:
                    text = chunk["text"]
                    references.append(
                        document_reference(
                            DocumentRead(
                                workspace_id=binding.native_workspace_id,
                                source_id=binding.native_id,
                                chunk_id=chunk["id"],
                                digest=sha256(text.encode()).hexdigest(),
                                quote=text[:8000],
                                page=chunk.get("page"),
                                section=(chunk.get("section_path") or "")[:512] or None,
                            ),
                            asset_id=document_id,
                            source_id=chain[1].id,
                            title=chain[0].name[:255],
                        )
                    )
                observed = CapturedEvidence(data, tuple(references), True)
                receipts = context.get_bean(ExternalReadReceipts)
                grant = await receipts.grant(principal, tenant_id)
                if "knowledge:search" not in grant.scopes:
                    return {**data, "read_receipt": not_recorded("source_reuse_scope_required")}
            else:
                raise ValueError("Only fixed evidence read operations are admitted")
            receipt = await context.get_bean(ExternalReadReceipts).record(
                principal, tenant_id, operation, arguments, observed
            )
            return {**observed.data, "read_receipt": receipt}

        async def work(principal):
            with reader_source_scope(principal, tenant_id, choices):
                if choices is not None:
                    await context.get_bean(SourceReader).begin(principal, tenant_id)
                return await execute(principal)

        try:
            return await authenticated_operation(context, raw, work)
        except SourceError:
            raise ToolError("Source read is unavailable or no longer authorized") from None

    return capture
