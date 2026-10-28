# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio

import pytest
from flycanon.core.services.query.provenance import current, observe, worker
from pyfly.kernel import ServiceUnavailableException

from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


async def test_exact_extraction_binds_content_reads_without_attesting_corpus_metadata():
    receipt = NativeEvidenceReceipt("owner", "tenant")
    with observe(receipt, tenant_id="tenant", workspace_id="workspace", actor="owner", source_ids={"source"}):
        scope = current()
        receipt.document_extraction("source", "version", "extraction", scope)
        receipt.document_sync("rlm.read", "Exact observed text", ("source",), scope)
        receipt.document_sync("rlm.corpus", "File title", ("source",), scope)
        used, metadata = receipt.native_reads
        assert (used.source_version_id, used.extraction_id, used.read_kind) == (
            "version",
            "extraction",
            "document_extraction",
        )
        assert metadata.source_version_id is None and metadata.extraction_id is None
        assert metadata.read_kind == "metadata"
        with pytest.raises(ServiceUnavailableException):
            receipt.document_extraction("source", "changed-version", "new-extraction", scope)
        assert receipt.native_reads[0] == used
    with pytest.raises(ServiceUnavailableException):
        receipt.document_extraction("source", "version", "extraction", scope)


async def test_only_current_request_or_leased_worker_can_register_extraction_ids():
    receipt = NativeEvidenceReceipt("owner", "tenant")
    with observe(receipt, tenant_id="tenant", workspace_id="workspace", actor="owner", source_ids={"source"}):
        scope = current()

        async def child():
            with pytest.raises(ServiceUnavailableException):
                receipt.document_extraction("source", "version", "extraction", scope)

        await asyncio.create_task(child())
        with pytest.raises(ServiceUnavailableException):
            await asyncio.to_thread(receipt.document_extraction, "source", "version", "extraction", scope)
        await asyncio.to_thread(
            worker(lambda: receipt.document_extraction("source", "version", "extraction", scope))
        )
        with pytest.raises(ServiceUnavailableException):
            receipt.document_extraction("foreign", "version", "extraction", scope)


def test_public_receipt_requires_coherent_document_extraction_pair():
    from pydantic import ValidationError

    from koinon.assistants.audit_dtos import NativeReadReceipt

    values = dict(
        result_id="result",
        stage="rlm.read",
        domain="documents",
        tenant_id="tenant",
        workspace_id="workspace",
        entity_id="document",
        content_sha256="a" * 64,
        source_ids=["native-source"],
        read_kind="document_extraction",
        source_version_id="version",
        extraction_id="extraction",
    )
    assert NativeReadReceipt(**values).extraction_id == "extraction"
    for changes in (
        {"extraction_id": None},
        {"read_kind": "metadata"},
        {"domain": "structured"},
        {"source_ids": []},
    ):
        with pytest.raises(ValidationError):
            NativeReadReceipt(**(values | changes))
