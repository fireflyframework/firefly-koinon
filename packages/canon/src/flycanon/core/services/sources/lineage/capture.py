# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Capture observed transformations and exact emitted sections/chunks."""

import inspect
from hashlib import sha256
from uuid import uuid4

from flycanon.core.services.ingestion.chunker import ParagraphChunker
from flycanon.core.services.sources.lineage.service import identity


def signature(component):
    kind = component if inspect.isfunction(component) else type(component)
    try:
        digest = sha256(inspect.getsource(kind).encode()).hexdigest()
    except (OSError, TypeError):
        digest = None
    result = {
        "class": f"{kind.__module__}.{kind.__qualname__}",
        "implementation_sha256": digest,
        "configuration_recorded": False,
    }
    if kind is ParagraphChunker:
        result["configuration"] = {
            key: getattr(component, key) for key in ("chunk_size_tokens", "overlap_tokens", "tokens_per_char")
        }
        result["configuration_recorded"] = True
    return result


async def artifact(lineage, scope, source_id, content, role, media_type):
    identifier = str(uuid4())
    record = {
        "id": identifier,
        **identity(scope, source_id),
        "role": role,
        "sha256": sha256(content).hexdigest(),
        "bytes": len(content),
        "media_type": media_type,
        "object_key": (
            f"koinon/{scope.tenant_id}/{scope.workspace_id}/document-lineage/{source_id}/{identifier}"
        ),
    }
    await lineage.store.put(record["object_key"], content, media_type)
    await lineage._verified(record, len(content))
    return record


def manifest(scope, admission, result, extraction_id, artifact_id):
    base = {
        **identity(scope, admission.source_id),
        "extraction_id": extraction_id,
        "artifact_id": artifact_id,
    }
    parts, section_ids = [], []
    for index, section in enumerate(result.sections):
        identifier = str(uuid4())
        section_ids.append(identifier)
        parts.append(
            {
                "id": identifier,
                **base,
                "kind": "section",
                "parent_id": None,
                "ordinal": index,
                "text": section.body,
                "sha256": sha256(section.body.encode()).hexdigest(),
                "page": section.page,
                "section_path": list(section.path),
                "char_start": None,
                "char_end": None,
                "offset_basis": None,
                "projection_chunk_id": None,
            }
        )
    for index, chunk in enumerate(result.chunks):
        if not chunk.id:
            chunk.id = str(uuid4())
        section_index = (
            result.chunk_section_indices[index] if index < len(result.chunk_section_indices) else None
        )
        parent = (
            section_ids[section_index]
            if section_index is not None and 0 <= section_index < len(section_ids)
            else None
        )
        parts.append(
            {
                "id": str(uuid4()),
                **base,
                "kind": "chunk",
                "parent_id": parent,
                "ordinal": index,
                "text": chunk.content,
                "sha256": sha256(chunk.content.encode()).hexdigest(),
                "page": chunk.page,
                "section_path": chunk.section_path,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "offset_basis": "emitted_stream_unicode_codepoints",
                "projection_chunk_id": chunk.id,
            }
        )
    return parts
