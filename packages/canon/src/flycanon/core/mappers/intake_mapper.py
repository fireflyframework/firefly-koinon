# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure source metadata and normalized-document representations."""

from typing import Any

from pyfly.agentic.content.binary import BinaryArtifact

from flycanon.core.services.ingestion import LoadedDocument
from flycanon.interfaces.dtos.source import SourceMetadata


def _metadata_to_json(metadata: SourceMetadata) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if metadata.title:
        payload["title"] = metadata.title
    if metadata.author:
        payload["author"] = metadata.author
    if metadata.domain is not None:
        payload["domain"] = metadata.domain.value
    if metadata.jurisdiction is not None:
        payload["jurisdiction"] = metadata.jurisdiction.value
    if metadata.language:
        payload["language"] = metadata.language
    if metadata.tags:
        payload["tags"] = list(metadata.tags)
    if metadata.extra:
        payload.update(metadata.extra)
    return payload


def _ancestry_metadata(artifacts: list[BinaryArtifact]) -> dict[str, Any]:
    return {
        "artifacts": [
            {
                "filename": artifact.filename,
                "kind": artifact.kind,
                "media_type": artifact.media_type,
                "derived_from": list(artifact.derived_from),
            }
            for artifact in artifacts
        ]
    }


def _render_document(
    document: LoadedDocument,
    *,
    artifact_label: str,
    index: int,
) -> str:
    if not document.sections:
        if document.raw_text:
            return f"## Artifact: {artifact_label}\n\n{document.raw_text.strip()}"
        return ""
    rendered_sections: list[str] = [f"## Artifact: {artifact_label}"]
    if document.title:
        rendered_sections.append(f"### {document.title}")
    for section in document.sections:
        if section.path:
            for level, heading in enumerate(section.path, start=3):
                rendered_sections.append(f"{'#' * min(level, 6)} {heading}")
        rendered_sections.append(section.body.strip())
    return "\n\n".join(rendered_sections)
