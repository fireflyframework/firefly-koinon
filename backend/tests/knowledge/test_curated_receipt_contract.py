# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError

from koinon.assistants.audit_dtos import NativeReadReceipt
from koinon.evidence.dtos import SourceReference


def test_knowledge_source_cannot_masquerade_as_a_document_or_infer_a_version():
    values = {
        "id": "reference",
        "asset_id": "canonical",
        "kind": "knowledge_version",
        "title": "Fact",
        "knowledge_item_id": "canonical",
        "knowledge_version_id": "native-version",
        "knowledge_version": 2,
        "chunk_id": "real-version-chunk",
        "used_revision": "knowledge-content-sha256:" + "a" * 64,
    }
    assert SourceReference.model_validate(values).source_id is None
    for change in (
        {"knowledge_version_id": None},
        {"knowledge_item_id": "foreign"},
        {"source_id": "fake-document"},
        {"used_revision": "chunk-sha256:" + "a" * 64},
        {"kind": "document"},
    ):
        with pytest.raises(ValidationError):
            SourceReference.model_validate({**values, **change})


def test_native_knowledge_read_has_explicit_canonical_scope_and_no_document_extraction():
    values = {
        "result_id": "result",
        "stage": "answer",
        "domain": "knowledge",
        "tenant_id": "north",
        "workspace_id": "canonical-space",
        "entity_id": "canonical",
        "content_sha256": "b" * 64,
        "source_ids": ["canonical"],
        "knowledge_item_id": "canonical",
        "knowledge_version_id": "native-version",
        "knowledge_version": 2,
        "read_kind": "knowledge_version",
    }
    assert NativeReadReceipt.model_validate(values).snapshot_ids == []
    for change in (
        {"knowledge_version": None},
        {"entity_id": "foreign"},
        {"domain": "documents"},
        {"source_ids": ["foreign"]},
        {"source_version_id": "document-version", "extraction_id": "extraction"},
    ):
        with pytest.raises(ValidationError):
            NativeReadReceipt.model_validate({**values, **change})
