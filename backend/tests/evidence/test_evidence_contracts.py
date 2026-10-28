# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from koinon.evidence.dtos import ConversationMessage, ConversationSnapshot, SourceReference, StoredResult


def test_snapshot_rejects_private_attachment_metadata_and_nonfinal_messages():
    with pytest.raises(ValidationError):
        ConversationMessage(id="m", role="assistant", text="Answer", status="running", revision="a" * 64)
    with pytest.raises(ValidationError):
        ConversationMessage(
            id="m",
            role="assistant",
            text="Answer",
            status="completed",
            revision="a" * 64,
            attachment_url="https://untrusted.invalid/private",
        )


def test_snapshot_is_bounded_revision_pinned_and_typed():
    message = ConversationMessage(
        id="m", role="assistant", text="Answer", status="completed", revision="a" * 64
    )
    snapshot = ConversationSnapshot(
        thread_id="t",
        tenant_id="north",
        owner_subject="issuer|owner",
        title="Research",
        revision="b" * 64,
        messages=(message,),
        sources=(),
    )
    assert snapshot.messages[0].text == "Answer"
    with pytest.raises(ValidationError):
        snapshot.title = "Changed"
    with pytest.raises(ValidationError):
        ConversationSnapshot(**{**snapshot.model_dump(), "messages": [message] * 201})


def test_source_revision_cannot_pretend_processing_offsets_are_original_coordinates():
    source = SourceReference(
        id="citation",
        asset_id="document",
        title="Policy",
        kind="document",
        used_revision="a" * 64,
        chunk_id="chunk",
        page=2,
        section="Eligibility",
    )
    assert source.page == 2
    with pytest.raises(ValidationError):
        SourceReference(**{**source.model_dump(), "original_start": 123})


def test_stored_result_keeps_truncation_and_aware_expiry_without_storage_urls():
    result = StoredResult(
        query_id="q",
        asset_id="dataset",
        revision="a" * 64,
        row_count=1000,
        row_cap=1000,
        truncated=True,
        completeness="bounded",
        byte_size=4096,
        columns=(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert result.truncated and result.completeness == "bounded"
    with pytest.raises(ValidationError):
        StoredResult(**{**result.model_dump(), "storage_url": "file:///private/key"})


def test_legacy_result_does_not_guess_historical_cap_or_truncation():
    result = StoredResult(
        query_id="q",
        asset_id="d",
        revision="a" * 64,
        row_count=100,
        row_cap=None,
        truncated=None,
        byte_size=1024,
        columns=(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert result.completeness == "unknown" and result.truncated is None


def test_missing_historical_metadata_cannot_be_labeled_bounded_and_complete():
    with pytest.raises(ValidationError):
        StoredResult(
            query_id="q",
            asset_id="d",
            revision="a" * 64,
            row_count=100,
            row_cap=None,
            truncated=None,
            completeness="bounded",
            byte_size=1024,
            columns=(),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
