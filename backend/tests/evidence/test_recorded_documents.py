# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Recorded reads accept retained context, never caller-supplied evidence authority."""

import pytest
from pydantic import ValidationError


@pytest.mark.parametrize(
    "context",
    [
        {"kind": "run", "run_id": "run", "message_id": "message", "reader_source_connections": []},
        {
            "kind": "conversation",
            "thread_id": "thread",
            "message_ids": ["same", "same"],
            "expected_manifest_revision": "a" * 64,
        },
        {"kind": "share", "share_id": "share", "message_ids": ["message"], "expected_revision": "a" * 64},
    ],
)
def test_recorded_context_rejects_ambiguous_or_forged_authority(context):
    from koinon.evidence.recorded_dtos import RecordedDocumentReadInput

    with pytest.raises(ValidationError):
        RecordedDocumentReadInput(source_reference_id="source", context=context)


def test_share_requires_deliberate_nullable_selection_and_owner_forbids_document_pins():
    from koinon.evidence.recorded_dtos import RecordedDocumentReadInput

    request = RecordedDocumentReadInput(
        source_reference_id="source",
        context={
            "kind": "share",
            "share_id": "share",
            "message_ids": ["message"],
            "expected_revision": "a" * 64,
            "reader_source_connections": None,
        },
    )
    assert request.model_dump()["context"]["reader_source_connections"] is None
    with pytest.raises(ValidationError):
        RecordedDocumentReadInput(
            source_reference_id="source",
            context={
                "kind": "run",
                "run_id": "run",
                "message_id": "message",
            },
            document_id="forged",
        )
