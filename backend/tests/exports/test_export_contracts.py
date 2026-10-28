# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import TypeAdapter, ValidationError

from koinon.exports.dtos import ExportCreate, ExportReviewInput


def test_export_formats_do_not_promise_pdf_or_complete_unbounded_results():
    adapter = TypeAdapter(ExportReviewInput)
    result = adapter.validate_python(
        {"kind": "query_result", "dataset_id": "d", "query_id": "q", "format": "parquet"}
    )
    assert result.kind == "query_result"
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"kind": "conversation", "thread_id": "t", "message_ids": ["m"], "format": "pdf"}
        )
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "kind": "query_result",
                "dataset_id": "d",
                "query_id": "q",
                "format": "csv",
                "storage_url": "file:///private",
            }
        )


def test_creation_requires_exact_review_revision_and_unique_selected_messages():
    with pytest.raises(ValidationError):
        ExportCreate(review_id="r", expected_revision="old")
    with pytest.raises(ValidationError):
        TypeAdapter(ExportReviewInput).validate_python(
            {"kind": "conversation", "thread_id": "t", "message_ids": ["m", "m"], "format": "json"}
        )
