# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read one verified version; stale source hashes never join its vectors."""

from uuid import UUID

from sqlalchemy import text

from flyquery.models.repositories.embedding_set_repository import OBJECTS_SQL
from flyquery.web.conventions.context import current_tenant_context


def parameters(binding, embedding, limit):
    context = current_tenant_context()
    if context is None or len(embedding) != binding.storage_dimensions:
        raise ValueError("A scoped compatible versioned retrieval binding is required")
    return {
        "tenant": context.tenant_id,
        "workspace": UUID(context.workspace_id),
        "set_id": binding.space_id,
        "emb": str(embedding),
        "lim": limit,
    }


async def schema_rows(session, binding, embedding, dataset_id, limit):
    params = {**parameters(binding, embedding, limit), "ds": dataset_id}
    await session.execute(text("SET LOCAL hnsw.iterative_scan='strict_order'"))
    rows = await session.execute(
        text(
            OBJECTS_SQL
            + """
        SELECT o.id,o.qualified_name,o.description,o.data_type,o.table_id,o.kind,o.snapshot_id,
               o.profile_json,o.sample_values_json,o.governance_json,
               1-(v.embedding <=> CAST(:emb AS vector)) AS score
        FROM flyquery_schema_objects o JOIN flyquery_tables t ON t.id=o.table_id
        JOIN objects fresh ON fresh.id=o.id AND fresh.kind='schema'
        JOIN flyquery_embedding_vectors v ON v.set_id=:set_id AND v.kind='schema'
          AND v.object_id=o.id AND v.content_hash=fresh.source_hash
          AND v.tenant_id=:tenant AND v.workspace_id=:workspace
        WHERE t.dataset_id=:ds AND t.is_active=true AND o.is_active=true
          AND o.snapshot_id=t.current_snapshot_id
        ORDER BY v.embedding <=> CAST(:emb AS vector) LIMIT :lim
    """
        ),
        params,
    )
    return rows.mappings().all()


async def example_rows(session, binding, embedding, workspace_id, dataset_id, limit):
    params = parameters(binding, embedding, limit)
    if str(params["workspace"]) != str(workspace_id):
        raise ValueError("Example retrieval workspace differs from its native scope")
    condition = "AND e.dataset_id=:ds" if dataset_id is not None else ""
    if dataset_id is not None:
        params["ds"] = dataset_id
    await session.execute(text("SET LOCAL hnsw.iterative_scan='strict_order'"))
    rows = await session.execute(
        text(
            OBJECTS_SQL
            + """
        SELECT e.id,e.question,e.generated_sql,1-(v.embedding <=> CAST(:emb AS vector)) AS score
        FROM flyquery_examples e JOIN objects fresh ON fresh.id=e.id AND fresh.kind='example'
        JOIN flyquery_embedding_vectors v ON v.set_id=:set_id AND v.kind='example'
          AND v.object_id=e.id AND v.content_hash=fresh.source_hash
          AND v.tenant_id=:tenant AND v.workspace_id=:workspace
        WHERE e.workspace_id=:workspace AND e.quality = 'APPROVED'
    """
            + condition
            + " ORDER BY v.embedding <=> CAST(:emb AS vector) LIMIT :lim"
        ),
        params,
    )
    return rows.mappings().all()
