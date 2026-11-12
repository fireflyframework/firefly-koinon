# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""SQL-only local-origin classification before saved-evidence filters and exact counts."""

from sqlalchemy import and_, cast, exists, func, literal, or_, select, true, union_all
from sqlalchemy.dialects.postgresql import JSONB

from koinon.assistants.entities import ChatRun, ChatThread, ToolResult
from koinon.assistants.memory.entities import ChatMemoryManifest
from koinon.catalog.entities import CatalogEntry
from koinon.catalog.repositories import local_catalog_entries


def local_saved_evidence(tenant, review, *, dialect="postgresql"):
    """Unknown, mixed, direct and remembered imported ancestry never reaches legacy counts."""

    def value(document, *path):
        if dialect == "sqlite":
            return func.json_extract(document, "$." + ".".join(path))
        result = cast(document, JSONB)
        for part in path:
            result = result[part]
        return result.astext

    def array(document, *path):
        if dialect == "sqlite":
            selected = func.json_extract(document, "$." + ".".join(path)) if path else document
            return func.json_each(func.coalesce(selected, "[]")).table_valued("value")
        selected = cast(document, JSONB)
        for part in path:
            selected = selected[part]
        return func.jsonb_array_elements(func.coalesce(selected, cast(literal("[]"), JSONB))).table_valued(
            "value"
        )

    local_ids = select(CatalogEntry.id).where(
        CatalogEntry.tenant_id == tenant, local_catalog_entries(tenant, CatalogEntry)
    )

    def nonlocal_reference(reference):
        identifier = value(reference, "asset_id")
        return or_(identifier.is_(None), identifier.not_in(local_ids))

    direct = array(review.manifest_json)
    direct_bad = exists(select(literal(1)).select_from(direct).where(nonlocal_reference(direct.c.value)))
    bindings = array(review.snapshot_json, "memory_bindings")
    generation_ids = select(value(bindings.c.value, "generation_id")).select_from(bindings)
    manifests = (
        select(ChatMemoryManifest.generation_id)
        .where(
            ChatMemoryManifest.tenant_id == tenant,
            ChatMemoryManifest.subject == review.owner_subject,
            ChatMemoryManifest.run_id == value(bindings.c.value, "run_id"),
            ChatMemoryManifest.generation_id == value(bindings.c.value, "generation_id"),
            ChatMemoryManifest.manifest_sha256 == value(bindings.c.value, "manifest_sha256"),
        )
        .correlate(review, bindings)
    )
    missing_manifest = exists(
        select(literal(1))
        .select_from(bindings)
        .where(value(bindings.c.value, "generation_id").is_not(None), ~exists(manifests))
    )

    direct_pins = array(bindings.c.value, "results")
    requests = [
        select(
            value(direct_pins.c.value, "id").label("id"), value(bindings.c.value, "run_id").label("run_id")
        )
        .select_from(bindings)
        .join(direct_pins, true())
    ]
    for key in ("dependencies", "turns"):
        dependencies = array(ChatMemoryManifest.manifest_json, key)
        pins = array(dependencies.c.value, "result_pins")
        requests.append(
            select(
                value(pins.c.value, "id").label("id"), value(dependencies.c.value, "run_id").label("run_id")
            )
            .select_from(ChatMemoryManifest)
            .join(dependencies, true())
            .join(pins, true())
            .where(
                ChatMemoryManifest.tenant_id == tenant,
                ChatMemoryManifest.subject == review.owner_subject,
                ChatMemoryManifest.generation_id.in_(generation_ids),
            )
            .correlate(review)
        )
    requested = union_all(*requests).subquery()
    known_result_ids = (
        select(ToolResult.id)
        .join(ChatRun, ChatRun.id == ToolResult.run_id)
        .join(ChatThread, ChatThread.id == ChatRun.thread_id)
        .where(
            ChatRun.tenant_id == tenant,
            ChatThread.tenant_id == tenant,
            ChatThread.subject == review.owner_subject,
            ToolResult.run_id == requested.c.run_id,
        )
        .correlate(review, requested)
    )
    missing_result = exists(
        select(literal(1))
        .select_from(requested)
        .where(or_(requested.c.id.is_(None), requested.c.id.not_in(known_result_ids)))
    )
    wanted = select(requested.c.id)
    result_bad = []
    for path in (("source_manifest", "sources"), ("release", "source_refs")):
        references = array(ToolResult.payload, *path)
        result_bad.append(
            exists(
                select(literal(1))
                .select_from(ToolResult)
                .join(ChatRun, ChatRun.id == ToolResult.run_id)
                .join(references, true())
                .where(
                    ChatRun.tenant_id == tenant,
                    ToolResult.id.in_(wanted),
                    nonlocal_reference(references.c.value),
                )
            )
        )
    complete = value(ToolResult.payload, "source_manifest", "complete")
    unknown_result = exists(
        select(literal(1))
        .select_from(ToolResult)
        .join(ChatRun, ChatRun.id == ToolResult.run_id)
        .where(
            ChatRun.tenant_id == tenant,
            ToolResult.id.in_(wanted),
            ToolResult.kind.in_(("search", "query", "schema", "lineage")),
            or_(complete.is_(None), complete.not_in(("true", "1") if dialect != "sqlite" else (1,))),
        )
    )

    message_ids = array(review.snapshot_json, "messages")
    unbound_memory = exists(
        select(literal(1))
        .select_from(ChatMemoryManifest)
        .join(ChatRun, ChatRun.id == ChatMemoryManifest.run_id)
        .where(
            ChatMemoryManifest.tenant_id == tenant,
            ChatRun.tenant_id == tenant,
            ChatRun.thread_id == value(review.snapshot_json, "thread_id"),
            ChatRun.message_id.in_(select(value(message_ids.c.value, "id")).select_from(message_ids)),
            ChatMemoryManifest.generation_id.not_in(generation_ids),
        )
    )
    return and_(
        ~direct_bad,
        ~missing_manifest,
        ~missing_result,
        ~unknown_result,
        ~unbound_memory,
        *(~condition for condition in result_bad),
    )
