# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Replay exact curated RLM input manifests and citations without querying current content."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flycanon.core.services.query.rlm.knowledge_integrity import verify_view

from koinon.knowledge.curated.rlm_mappers import fingerprint, part_source
from koinon.knowledge.curated.rlm_receipts import MODELS, VIEW, execution_views
from koinon.knowledge.rlm_provenance import EXECUTION_READ, unavailable

if TYPE_CHECKING:
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


def metadata_for_read(receipt: NativeEvidenceReceipt, row):
    found = [
        meta
        for meta in receipt.curated_rlm.metadata.values()
        if (meta.canonical_workspace_id, meta.item_id) == (row.workspace_id, row.entity_id)
    ]
    if len(found) != 1:
        raise unavailable()
    meta = found[0]
    if (
        row.domain != "knowledge"
        or row.tenant_id != receipt.tenant_id
        or row.source_ids != (meta.item_id,)
        or row.snapshot_ids
        or row.read_kind != "knowledge_version"
        or row.knowledge_item_id != meta.item_id
        or row.knowledge_version_id != meta.version_id
        or row.knowledge_version != meta.version
        or row.source_version_id is not None
        or row.extraction_id is not None
    ):
        raise unavailable()
    return meta


def verified(receipt: NativeEvidenceReceipt, data: dict) -> bool:
    state = receipt.curated_rlm
    parts = {part.part_id: (key, view, part) for key, view in state.views.items() for part in view.parts}
    expected = {
        identifier: part_source(view.meta, identifier, part.text)
        for identifier, (_, view, part) in parts.items()
    }
    if set(expected) != set(receipt.knowledge_sources) or any(
        receipt.knowledge_sources[k] != v for k, v in expected.items()
    ):
        raise unavailable()
    for key, view in state.views.items():
        verify_view(view)
        if state.metadata.get(key) != view.meta:
            raise unavailable()
    manifests, reads, models, released = set(), set(), set(), set()
    for row in receipt.native_reads:
        if row.domain != "knowledge":
            continue
        meta = metadata_for_read(receipt, row)
        key = (meta.workspace_id, meta.item_id)
        view = state.views.get(key)
        if row.stage in {VIEW, "rlm.read", EXECUTION_READ}:
            if view is None:
                raise unavailable()
            digest = view.manifest_sha256 if row.stage == VIEW else meta.body_sha256
            if row != fingerprint(meta, row.stage, digest, view):
                raise unavailable()
            if row.stage == VIEW:
                manifests.add(key)
            elif key not in manifests:
                raise unavailable()
            elif row.stage == "rlm.read":
                reads.add(key)
            elif key not in reads:
                raise unavailable()
            else:
                released.add(key)
        elif row.stage in {"rlm.corpus", *MODELS}:
            if row != fingerprint(meta, row.stage, row.content_sha256, view if key in manifests else None):
                raise unavailable()
            if row.stage in {"rlm.root", "rlm.forced_final"}:
                models.add(key)
        else:
            raise unavailable()
    if (
        set(state.views) - manifests
        or set(state.views) - reads
        or set(state.views) - models
        or released != execution_views(receipt)
        or set(state.execution) != released
    ):
        return False
    valid = True
    for citation in data["citations"]:
        if citation.get("source_kind") != "knowledge_version":
            continue
        found = parts.get(citation.get("chunk_id"))
        if found is None:
            raise unavailable()
        key, view, part = found
        meta = view.meta
        metadata = citation.get("metadata") or {}
        if (
            (
                citation.get("asset_id"),
                citation.get("knowledge_item_id"),
                citation.get("knowledge_version_id"),
                citation.get("knowledge_version"),
            )
            != (meta.item_id, meta.item_id, meta.version_id, meta.version)
            or citation.get("source_id") is not None
            or citation.get("page") is not None
            or any(
                citation.get(name) is not None or metadata.get(name) is not None
                for name in (
                    "source_version_id",
                    "extraction_id",
                    "source_part_id",
                    "recorded_page",
                    "page_basis",
                )
            )
            or metadata.get("knowledge_content_sha256") != meta.content_sha256
            or metadata.get("knowledge_part_sha256") != part.sha256
            or not isinstance(citation.get("content"), str)
            or not citation["content"]
            or citation["content"] not in part.text
        ):
            raise unavailable()
        valid = valid and key in released
    return valid
