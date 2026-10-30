# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon_sdk import SearchHit, SourceReference


def test_search_hit_retains_a_typed_source_reference_and_accepts_legacy_absence():
    saved = dict(
        id="evidence",
        asset_id="document",
        source_id="catalog-source",
        title="Historical title",
        kind="document",
        source_version_id="version",
        extraction_id="extraction",
        source_part_id="part",
        source_part_sha256="a" * 64,
        recorded_page=7,
        page_basis="recorded_loader",
        chunk_id=None,
        quote="retained",
        availability="available",
    )
    hit = dict(
        id="projection",
        title="Historical title",
        text="retained",
        asset_id="document",
        source_id="catalog-source",
    )
    recorded = SearchHit.model_validate({**hit, "source_reference": saved})
    assert isinstance(recorded.source_reference, SourceReference)
    assert recorded.source_reference.source_version_id == "version"
    assert recorded.source_reference.extraction_id == "extraction"
    assert recorded.source_reference.source_part_id == "part"
    assert recorded.source_reference.chunk_id is None
    assert SearchHit.model_validate(hit).source_reference is None
