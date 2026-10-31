# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit, reusable transformation stages without parent-service access."""

from __future__ import annotations

import logging
from typing import Any

from pyfly.agentic.content.binary import BinaryArtifact

from flycanon.core.mappers.intake_mapper import _ancestry_metadata, _render_document
from flycanon.core.services.embeddings import (
    EmbeddingRegistry,
    EmbeddingService,
    EmbeddingSetBinding,
    EmbeddingSetService,
)
from flycanon.core.services.ingestion.loaders import LoaderRegistry
from flycanon.core.services.pii import PiiPolicy, PiiPolicyViolation, PiiScanner
from flycanon.core.services.pii.scanner import redact as pii_redact
from flycanon.interfaces.enums import SourceKind

logger = logging.getLogger(__name__)


def apply_pii_policy(
    content: bytes,
    metadata: dict[str, Any],
    *,
    policy: PiiPolicy,
    scanner: PiiScanner | None,
) -> tuple[bytes, dict[str, Any]]:
    """Run the configured PII scan against ``content`` and apply the policy.

    Returns ``(possibly-redacted-content, metadata-with-findings)``.
    The scanner operates on the merged text (decoded UTF-8) so a
    contaminated child artefact in an archive triggers the same
    policy as a top-level hit. Raises :class:`PiiPolicyViolation`
    when the policy is ``reject`` and findings are non-empty.
    """
    if scanner is None or policy == PiiPolicy.disabled:
        return content, metadata
    text_view = decode_for_scan(content)
    findings = scanner.scan(text_view)
    if not findings:
        return content, metadata
    if policy == PiiPolicy.reject:
        raise PiiPolicyViolation(findings)
    if policy == PiiPolicy.redact:
        redacted = pii_redact(text_view, findings)
        content = redacted.encode("utf-8")
    metadata.setdefault(
        "pii_findings",
        [{"kind": f.kind, "start": f.start, "end": f.end} for f in findings],
    )
    return content, metadata


def decode_for_scan(content: bytes) -> str:
    """Best-effort UTF-8 decode for the PII scanner.

    Binary payloads (PDFs in their canonical form, images,
    archives that didn't get expanded inline) decode as
    ``replace`` -- the scanner runs against the parts of the
    stream that ARE text, and the binary spans become
    unmatchable byte runs.
    """
    try:
        return content.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        return content.decode("utf-8", errors="replace") if isinstance(content, bytes) else ""


def first_text(chunks: list[Any]) -> str:
    """Return up to ~2 000 chars of the first ingested chunk's
    text so the language detector has something to work with.
    """
    if not chunks:
        return ""
    body = getattr(chunks[0], "content", "") or ""
    return body[:2000]


def merge_artifacts(
    artifacts: list[BinaryArtifact],
    original_filename: str | None,
    loaders: LoaderRegistry,
    observer=None,
) -> tuple[SourceKind, bytes, dict[str, Any]]:
    """Collapse a fan-out artifact list into a single content payload.

    Single-artifact intakes pass through unchanged. Multi-artifact
    intakes (archives, emails with attachments) get merged into
    one Markdown document with ``## Artifact: <filename>`` section
    markers separating constituents -- the chunker treats each
    constituent as a sibling section, and the citation graph
    records the ancestry on the source row's metadata.
    """
    if len(artifacts) == 1:
        artifact = artifacts[0]
        return SourceKind(artifact.kind), artifact.bytes, _ancestry_metadata([artifact])

    merged_sections: list[str] = []
    kind = SourceKind.archive
    for index, artifact in enumerate(artifacts):
        loader = loaders.get(SourceKind(artifact.kind))
        if loader is None:
            if observer is not None:
                observer(index, None, False, "loader_unavailable")
            logger.warning(
                "intake skipping artifact kind=%s filename=%s -- no loader",
                artifact.kind,
                artifact.filename,
            )
            continue
        try:
            document = loader.load(artifact.bytes, filename=artifact.filename)
        except Exception as exc:
            if observer is not None:
                observer(index, None, False, "loader_failed")
            logger.warning(
                "intake skipping artifact kind=%s filename=%s -- loader failed: %s",
                artifact.kind,
                artifact.filename,
                exc,
            )
            continue
        rendered = _render_document(document, artifact_label=artifact.filename, index=index)
        if rendered:
            merged_sections.append(rendered)
        if observer is not None:
            observer(index, document, bool(rendered), None if rendered else "empty_extraction")

    merged = "\n\n".join(merged_sections).encode("utf-8")
    return kind, merged, _ancestry_metadata(artifacts)


async def embedder_for(
    *,
    tenant_id: str,
    workspace_id: str,
    embeddings: EmbeddingService,
    embedding_sets: EmbeddingSetService | None = None,
    embedding_registry: EmbeddingRegistry | None = None,
) -> tuple[EmbeddingSetBinding | None, EmbeddingService]:
    """The workspace's embedding set and its embedder, minting the first set.

    A workspace's very first ingest creates a set from the process default
    and points the workspace at it, so a single-embedder deployment never
    chooses a set and still gets one that records what produced its
    vectors -- which is the whole point.
    """
    if embedding_sets is None or embedding_registry is None:
        return None, embeddings
    binding = await embedding_sets.ensure_active(tenant_id=tenant_id, workspace_id=workspace_id)
    return binding, embedding_registry.for_binding(binding)
