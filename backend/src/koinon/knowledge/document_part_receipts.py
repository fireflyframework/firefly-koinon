# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Verify a captured whole-view part through the immutable native reader."""

from hashlib import sha256

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.curated.source_scope import document_source_scope


async def verify_part(domains, subject, tenant_id, binding, reference, *, current=False):
    parts = await domains.document_parts(
        tenant_id=tenant_id,
        workspace_id=binding.native_workspace_id,
        source_id=binding.native_id,
        source_version_id=reference.source_version_id,
        extraction_id=reference.extraction_id,
        part_ids=(reference.source_part_id,),
        actor=subject,
    )
    if len(parts) != 1:
        raise AccessDenied("Exact document part is unavailable", code="EVIDENCE_UNAVAILABLE")
    part = parts[0]
    result = checked_part(binding, reference, part)
    if current:
        head = await domains.document_revision(
            tenant_id=tenant_id,
            workspace_id=binding.native_workspace_id,
            source_id=binding.native_id,
            actor=subject,
        )
        result = freshness(result, part, head)
    return result


def checked_part(binding, reference, part):
    if (
        (part.part_id, part.source_id, part.source_version_id, part.extraction_id, part.sha256)
        != (
            reference.source_part_id,
            binding.native_id,
            reference.source_version_id,
            reference.extraction_id,
            reference.source_part_sha256,
        )
        or sha256(part.text.encode()).hexdigest() != part.sha256
        or reference.quote is not None
        and reference.quote not in part.text
        or reference.recorded_page is not None
        and reference.recorded_page != part.page
    ):
        raise AccessDenied("Exact document part differs from its receipt", code="EVIDENCE_UNAVAILABLE")
    return reference.model_copy(
        update={"current_revision": "source-part-sha256:" + part.sha256, "availability": "available"}
    )


def freshness(reference, part, head):
    same = head is not None and (head.get("source_version_id"), head.get("extraction_id")) == (
        part.source_version_id,
        part.ingestion_extraction_id,
    )
    return reference.model_copy(
        update={
            "current_revision": reference.used_revision if same else None,
            "availability": "available" if same else "changed" if head is not None else "unverified",
        }
    )


async def verify_part_sources(
    domains, subject, tenant_id, references, *, current=False, lock=False, authorize=None
):
    groups, result = {}, {}
    for reference, binding in references:
        key = (
            binding.native_workspace_id,
            binding.native_id,
            reference.source_version_id,
            reference.extraction_id,
        )
        groups.setdefault(key, []).append((reference, binding))
    for (workspace, source, version, extraction), values in groups.items():
        async with document_source_scope(
            tenant_id, workspace, authorize=(lambda values=values: authorize(values)) if authorize else None
        ):
            ids = tuple(dict.fromkeys(reference.source_part_id for reference, _ in values))
            observed = {}
            for start in range(0, len(ids), 100):
                parts = await domains.document_parts(
                    tenant_id=tenant_id,
                    workspace_id=workspace,
                    source_id=source,
                    source_version_id=version,
                    extraction_id=extraction,
                    part_ids=ids[start : start + 100],
                    actor=subject,
                )
                observed.update({part.part_id: part for part in parts})
            if set(observed) != set(ids):
                raise AccessDenied("Exact document parts are unavailable", code="EVIDENCE_UNAVAILABLE")
            head = (
                await domains.document_revision(
                    tenant_id=tenant_id,
                    workspace_id=workspace,
                    source_id=source,
                    actor=subject,
                    **({"lock": True} if lock else {}),
                )
                if current
                else None
            )
            for reference, binding in values:
                part = observed[reference.source_part_id]
                checked = checked_part(binding, reference, part)
                result[reference.id] = freshness(checked, part, head) if current else checked
    return result
