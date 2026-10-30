# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Capture one real native read without replaying queries or accepting client source manifests."""

from hashlib import sha256

from pyfly.context import ApplicationContext

from koinon.knowledge.capture_dtos import CapturedEvidence, DocumentRead, NativeCaptureLimits
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence, document_reference
from koinon.knowledge.external_reviews.read_receipts import ExternalReadReceipts, not_recorded
from koinon.mcp.private_reviews import authenticated_operation


def native_read_capture(context: ApplicationContext):
    async def capture(raw: str, tenant_id: str, operation: str, arguments: dict):
        async def work(principal):
            native = context.get_bean(NativeKnowledgeEvidence)
            limits = NativeCaptureLimits(sources=64, receipt_bytes=262144)
            if operation == "search":
                observed = await native.search(principal, tenant_id, _limits=limits, **arguments)
            elif operation == "query":
                observed = await native.query(principal, tenant_id, _limits=limits, **arguments)
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

        return await authenticated_operation(context, raw, work)

    return capture
