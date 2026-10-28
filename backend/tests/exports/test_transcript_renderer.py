# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import pytest

from koinon.evidence.dtos import ConversationMessage, ConversationSnapshot, SourceReference
from koinon.exports.renderers import render_transcript


def snapshot():
    return ConversationSnapshot(
        thread_id="thread",
        tenant_id="north",
        owner_subject="issuer|private-owner",
        title="Research / 2026",
        revision="a" * 64,
        originating_token_ids=("private-token",),
        source_manifest_complete=True,
        messages=(
            ConversationMessage(
                id="m",
                role="assistant",
                text="Amount: 12345678901234567890.123400\n<script>alert(1)</script>",
                status="completed",
                revision="b" * 64,
                source_ids=("s",),
            ),
        ),
        sources=(
            SourceReference(
                id="s",
                asset_id="a",
                title="Quarterly report",
                kind="document",
                used_revision="c" * 64,
                page=3,
            ),
        ),
    )


def test_versioned_json_export_preserves_exact_text_but_excludes_internal_principal_token_fields():
    rendered = render_transcript(snapshot(), "json", include_evidence=True)
    data = json.loads(rendered.content)
    assert data["schema_version"] == 1 and data["completeness"] == "selected_messages"
    assert "12345678901234567890.123400" in data["messages"][0]["text"]
    assert data["sources"][0]["used_revision"] == "c" * 64
    assert b"private-owner" not in rendered.content and b"private-token" not in rendered.content
    assert rendered.filename == "research-2026.json"


def test_markdown_export_carries_sources_and_escapes_model_html():
    rendered = render_transcript(snapshot(), "markdown", include_evidence=True)
    text = rendered.content.decode()
    assert "Quarterly report" in text and "page 3" in text
    assert "12345678901234567890.123400" in text and "<script>" not in text
    assert "Selected messages" in text and "private-owner" not in text


def test_omitted_evidence_is_explicit_and_does_not_leak_quotes_or_reference_metadata():
    rendered = render_transcript(snapshot(), "json", include_evidence=False)
    data = json.loads(rendered.content)
    assert data["sources"] == [] and data["omissions"]
    assert "Quarterly report" not in rendered.content.decode()


def test_transcript_renderer_does_not_silently_accept_other_formats():
    with pytest.raises(ValueError):
        render_transcript(snapshot(), "pdf", include_evidence=True)


def test_markdown_escapes_source_reference_text_as_well_as_model_messages():
    value = snapshot()
    malicious = value.sources[0].model_copy(update={"id": "<script>reference</script>"})
    rendered = render_transcript(
        value.model_copy(update={"sources": (malicious,)}), "markdown", include_evidence=True
    )
    assert b"<script>" not in rendered.content
