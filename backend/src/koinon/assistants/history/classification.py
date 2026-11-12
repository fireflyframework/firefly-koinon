# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Classify local history in SQL before title search, hydration or exact counts."""

from sqlalchemy import and_, case, cast, exists, func, literal, or_, select, true, union_all
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import aliased

from koinon.assistants.entities import ChatMessage, ChatRun, ChatThread, ToolResult
from koinon.assistants.memory.entities import ChatMemoryManifest
from koinon.catalog.entities import CatalogEntry
from koinon.catalog.repositories import local_catalog_entries
from koinon.integrations.content_sources.read_repository import SourceReadRepository


def local_conversation(tenant, session):
    projection = SourceReadRepository(session=session)
    text = projection._text

    def values(document, *path):
        # Malformed ancestry must be excluded, not crash JSON expansion before the
        # corresponding shape predicate can reject it.
        if session.get_bind().dialect.name == "sqlite":
            selected = func.json_extract(document, "$." + ".".join(path)) if path else document
            safe = case((func.json_type(selected) == "array", selected), else_="[]")
            return func.json_each(safe).table_valued("value")
        selected = cast(document, JSONB)
        for key in path:
            selected = selected[key]
        safe = case((func.jsonb_typeof(selected) == "array", selected), else_=cast(literal("[]"), JSONB))
        return func.jsonb_array_elements(safe).table_valued("value").lateral()

    thread = ChatThread
    runs = (
        select(ChatRun.id)
        .where(ChatRun.thread_id == thread.id, ChatRun.tenant_id == tenant)
        .correlate(thread)
    )
    manifests = (
        select(ChatMemoryManifest.id)
        .where(
            ChatMemoryManifest.thread_id == thread.id,
            ChatMemoryManifest.tenant_id == tenant,
            ChatMemoryManifest.subject == thread.subject,
        )
        .correlate(thread)
    )
    owned_runs = (
        select(
            ChatRun.id.label("run_id"), ChatThread.id.label("thread_id"), ChatThread.subject.label("owner")
        )
        .join(ChatThread, ChatThread.id == ChatRun.thread_id)
        .where(ChatRun.tenant_id == tenant, ChatThread.tenant_id == tenant)
        .cte("history_owned_runs")
    )
    requested = [
        select(
            ToolResult.id.label("id"),
            ToolResult.run_id.label("run_id"),
            owned_runs.c.thread_id,
            owned_runs.c.owner,
        ).join(owned_runs, owned_runs.c.run_id == ToolResult.run_id)
    ]
    for key in ("dependencies", "turns"):
        dependencies = values(ChatMemoryManifest.manifest_json, key)
        pins = values(dependencies.c.value, "result_pins")
        requested.append(
            select(
                text(pins.c.value, "id").label("id"),
                text(dependencies.c.value, "run_id").label("run_id"),
                ChatMemoryManifest.thread_id,
                ChatMemoryManifest.subject.label("owner"),
            )
            .select_from(ChatMemoryManifest)
            .join(dependencies, true())
            .join(pins, true())
            .where(ChatMemoryManifest.tenant_id == tenant)
        )
    # Reuse the identity graph rather than inlining it once per authorization predicate.
    # Inlining made PostgreSQL compile many copies with JIT even for an empty conversation.
    requests = union_all(*requested).cte("history_requested_results")
    selected = (requests.c.thread_id == thread.id, requests.c.owner == thread.subject)
    wanted = select(requests.c.id).where(*selected).correlate(thread)
    owner_thread = aliased(ChatThread)
    known = (
        select(ToolResult.id)
        .join(ChatRun, ChatRun.id == ToolResult.run_id)
        .join(owner_thread, owner_thread.id == ChatRun.thread_id)
        .where(
            ChatRun.tenant_id == tenant,
            ToolResult.run_id == requests.c.run_id,
            owner_thread.tenant_id == tenant,
            owner_thread.subject == requests.c.owner,
        )
        .correlate(requests)
    )
    missing = exists(
        select(literal(1))
        .select_from(requests)
        .where(*selected, or_(requests.c.id.is_(None), requests.c.id.not_in(known)))
        .correlate(thread)
    )
    local_entries = (
        select(CatalogEntry.id)
        .where(CatalogEntry.tenant_id == tenant, local_catalog_entries(tenant, CatalogEntry))
        .cte("history_local_assets")
    )
    local_ids = select(local_entries.c.id)
    bad = []
    for path in (("source_manifest", "sources"), ("release", "source_refs")):
        refs = values(ToolResult.payload, *path)
        identifier = text(refs.c.value, "asset_id")
        bad.append(
            exists(
                select(literal(1))
                .select_from(ToolResult)
                .join(refs, true())
                .where(ToolResult.id.in_(wanted), or_(identifier.is_(None), identifier.not_in(local_ids)))
            )
        )
        shape = projection._json_type(ToolResult.payload, *path)
        bad.append(
            exists(select(literal(1)).where(ToolResult.id.in_(wanted), shape.is_not(None), shape != "array"))
        )
    complete = ToolResult.payload["source_manifest"]["complete"].as_boolean()
    unknown = exists(
        select(literal(1)).where(
            ToolResult.id.in_(wanted),
            or_(
                ToolResult.kind.not_in(
                    (
                        "search",
                        "query",
                        "schema",
                        "lineage",
                        "generation",
                        "observation",
                        "answer_release",
                        "proposal",
                        "product_context",
                        "attachment",
                    )
                ),
                and_(
                    ToolResult.kind.in_(("search", "query", "schema", "lineage")),
                    or_(
                        complete.is_distinct_from(True),
                        projection._json_type(
                            ToolResult.payload, "source_manifest", "sources"
                        ).is_distinct_from("array"),
                    ),
                ),
            ),
        )
    )
    generations = select(ChatMemoryManifest.generation_id).where(ChatMemoryManifest.id.in_(manifests))
    missing_memory = exists(
        select(literal(1)).where(
            ToolResult.run_id.in_(runs),
            ToolResult.kind == "generation",
            ToolResult.payload["generation"]["status"].as_string().is_distinct_from("started"),
            ToolResult.id.not_in(generations),
        )
    )
    released = exists(
        select(ToolResult.id).where(ToolResult.run_id == ChatRun.id, ToolResult.kind == "answer_release")
    )
    unknown_answer = exists(
        select(ChatRun.id)
        .join(ChatMessage, ChatMessage.id == ChatRun.message_id)
        .where(ChatRun.thread_id == thread.id, ChatRun.tenant_id == tenant, ChatMessage.text != "", ~released)
        .correlate(thread)
    )
    malformed_memory = exists(
        select(ChatMemoryManifest.id).where(
            ChatMemoryManifest.id.in_(manifests),
            or_(
                projection._json_type(ChatMemoryManifest.manifest_json, "dependencies").is_distinct_from(
                    "array"
                ),
                projection._json_type(ChatMemoryManifest.manifest_json, "turns").is_distinct_from("array"),
            ),
        )
    )
    return and_(
        ~missing,
        ~unknown,
        ~missing_memory,
        ~unknown_answer,
        ~malformed_memory,
        *(~condition for condition in bad),
    )


async def local_history_filter(session, subject, tenant):
    """Empty/prompt-only histories need no derived-evidence graph query."""
    result = exists(
        select(ToolResult.id)
        .join(ChatRun, ChatRun.id == ToolResult.run_id)
        .join(ChatThread, ChatThread.id == ChatRun.thread_id)
        .where(ChatThread.subject == subject, ChatThread.tenant_id == tenant, ChatRun.tenant_id == tenant)
    )
    answer = exists(
        select(ChatMessage.id)
        .join(ChatThread, ChatThread.id == ChatMessage.thread_id)
        .where(
            ChatThread.subject == subject,
            ChatThread.tenant_id == tenant,
            ChatMessage.role == "assistant",
            ChatMessage.text != "",
        )
    )
    memory = exists(
        select(ChatMemoryManifest.id)
        .join(ChatThread, ChatThread.id == ChatMemoryManifest.thread_id)
        .where(ChatThread.subject == subject, ChatThread.tenant_id == tenant)
    )
    if not await session.scalar(select(or_(result, answer, memory))):
        return true()
    return local_conversation(tenant, session)
