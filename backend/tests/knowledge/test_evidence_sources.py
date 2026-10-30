# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.evidence_sources import NativeSourceResolver


def prepared():
    asset = SimpleNamespace(id="document", kind="document", name="Actual title")
    source = SimpleNamespace(id="source")
    binding = SimpleNamespace(native_id="native-source", native_workspace_id="native-workspace")
    knowledge = SimpleNamespace(
        _chain=AsyncMock(return_value=[asset, source]), binding=AsyncMock(return_value=binding)
    )
    repository = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(metadata_json={}, content_sha256="a" * 64)),
        get_many=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="chunk",
                    tenant_id="tenant",
                    workspace_id="native-workspace",
                    source_id="native-source",
                    content="Verified native quotation",
                    page=2,
                    section_path="Actual section",
                )
            ]
        ),
    )
    domains = SimpleNamespace(_resolve=lambda kind: repository)
    return NativeSourceResolver(knowledge, domains, SimpleNamespace()), knowledge, repository


async def test_source_replay_preserves_saved_presentation_and_unknown_historical_page():
    service, _, _ = prepared()
    ref = SourceReference(
        id="citation",
        asset_id="document",
        source_id="source",
        title="Recorded title",
        kind="document",
        chunk_id="chunk",
        quote="Verified native",
        used_revision="a" * 64,
    )
    (actual,) = await service.resolve("owner", "tenant", (ref,))
    assert actual.title == "Recorded title" and actual.quote == "Verified native"
    assert actual.current_revision == "a" * 64 and actual.availability == "available"
    assert actual.page is None and actual.section is None


async def test_mixed_foreign_source_is_denied_before_any_native_content_read():
    service, knowledge, repository = prepared()
    knowledge._chain.side_effect = [knowledge._chain.return_value, AccessDenied("Foreign")]
    refs = tuple(
        SourceReference(id=value, asset_id=value, title="Title", kind="document")
        for value in ("document", "foreign")
    )
    with pytest.raises(AccessDenied):
        await service.resolve("owner", "tenant", refs)
    repository.get.assert_not_awaited()


async def test_reingested_missing_chunk_never_becomes_a_fabricated_current_quote():
    service, _, repository = prepared()
    repository.get_many.return_value = []
    ref = SourceReference(
        id="old",
        asset_id="document",
        title="Old",
        kind="document",
        chunk_id="gone",
        quote="Old historical quote",
        used_revision="b" * 64,
    )
    (current,) = await service.resolve("owner", "tenant", (ref,))
    assert (
        current.availability == "changed"
        and current.current_revision == "a" * 64
        and current.quote == "Old historical quote"
    )


async def test_captured_chunk_revision_uses_exact_chunk_hash_not_current_original_metadata():
    from hashlib import sha256

    service, _, repository = prepared()
    repository.get.return_value.metadata_json = {"_persisted_original": {"sha256": "stale-original"}}
    original = repository.get_many.return_value[0].content
    used = "chunk-sha256:" + sha256(original.encode()).hexdigest()
    reference = SourceReference(
        id="captured",
        asset_id="document",
        title="Original title",
        kind="document",
        chunk_id="chunk",
        quote=original,
        used_revision=used,
        page=2,
        section="Actual section",
    )
    (current,) = await service.resolve("owner", "tenant", (reference,))
    assert current.used_revision == current.current_revision == used
    assert current.availability == "available"
    repository.get_many.return_value[0].content = "Changed native text"
    (changed,) = await service.resolve("owner", "tenant", (reference,))
    assert changed.availability == "changed" and changed.used_revision == used
    assert changed.current_revision == "chunk-sha256:" + sha256(b"Changed native text").hexdigest()
    assert changed.quote == original
    repository.get_many.return_value = []
    (missing,) = await service.resolve("owner", "tenant", (reference,))
    assert (
        missing.availability == "changed" and missing.current_revision is None and missing.quote == original
    )


async def test_legacy_native_read_never_fills_unrecorded_coordinates_from_current_chunks():
    service, knowledge, _ = prepared()
    ref = SourceReference(
        id="legacy", asset_id="document", title="Not recorded", kind="document", chunk_id="chunk",
        used_revision="a" * 64,
    )
    resolved = await service.document("owner", "tenant", ref, knowledge.binding.return_value)
    assert resolved["quote"] is None and resolved["page"] is None and resolved["section"] is None
    (actual,) = await service.resolve("owner", "tenant", (ref,))
    assert actual.source_id is None and actual.title == "Not recorded"
