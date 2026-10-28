# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Capture actual section identity instead of guessing it from heading text."""

from dataclasses import dataclass
from types import SimpleNamespace

from flycanon.core.services.ingestion.chunker import ParagraphChunker
from flycanon.core.services.ingestion.ingestion_service import IngestionService
from flycanon.core.services.ingestion.loaders import LoadedDocument, LoaderRegistry, Section
from flycanon.interfaces.enums import SourceKind
from flycanon.models.entities.source import SourceRow


def test_unknown_dataclass_configuration_never_serializes_credentials_or_callbacks():
    from flycanon.core.services.sources.lineage.capture import signature

    @dataclass
    class CustomLoader:
        api_key: str = "controlled-secret"
        endpoint: str = "https://private.invalid"

    result = signature(CustomLoader())
    assert "controlled-secret" not in str(result)
    assert "private.invalid" not in str(result)
    assert result["configuration_recorded"] is False


def test_paragraph_settings_are_observed_without_expanding_an_unknown_subclass():
    from flycanon.core.services.sources.lineage.capture import signature

    result = signature(ParagraphChunker(256, 32))
    assert result["configuration"] == {
        "chunk_size_tokens": 256,
        "overlap_tokens": 32,
        "tokens_per_char": 0.25,
    }
    assert result["configuration_recorded"] is True


def test_duplicate_heading_sections_keep_exact_emitted_chunk_parent_identity():
    sections = [Section(["Repeated"], "first body", page=1), Section(["Repeated"], "second body", page=2)]
    loader = SimpleNamespace(kind=SourceKind.text, load=lambda *args, **kwargs: LoadedDocument(sections))
    registry = LoaderRegistry()
    registry.register(loader)
    result = IngestionService(loaders=registry, chunker=ParagraphChunker()).ingest(
        source=SourceRow(id="s", tenant_id="t", workspace_id="w", kind="text", metadata_json={}),
        content=b"input",
        tenant_id="t",
        workspace_id="w",
    )
    assert result.sections == tuple(sections)
    assert result.chunk_section_indices == (0, 1)
