# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Publish new original schema/example content into its verified active version."""

from uuid import UUID

from pyfly.data.transaction import infrastructure_unit
from sqlalchemy import text

from flyquery.core.agents.model_bindings import embedding_for
from flyquery.models.repositories.embedding_set_repository import OBJECTS_SQL, EmbeddingSetRepository
from flyquery.web.conventions.context import current_tenant_context


async def write_active_vector(factory, *, tenant_id, object_id, kind, vector, source_hash=None):
    binding = embedding_for("structured.embedding")
    if binding is None or not binding.versioned or vector is None:
        return
    context = current_tenant_context()
    if context is None or context.tenant_id != tenant_id or len(vector) != 1536:
        raise ValueError("A compatible scoped active vector publication is required")
    if kind == "schema" and source_hash is None:
        raise ValueError("Schema embedding publication requires its pre-embedding content fingerprint")
    if source_hash is None:
        async with infrastructure_unit(factory) as session:
            source_hash = await session.scalar(
                text(OBJECTS_SQL + " SELECT source_hash FROM objects WHERE id=:object_id AND kind=:kind"),
                {
                    "tenant": tenant_id,
                    "workspace": UUID(context.workspace_id),
                    "object_id": object_id,
                    "kind": kind,
                },
            )
    if source_hash is not None:
        async with infrastructure_unit(factory) as session:
            from flyquery.core.services.retrieval.index_scope import guard_publication

            await guard_publication(session, binding)
            await EmbeddingSetRepository(factory).upsert(
                tenant_id=tenant_id,
                workspace_id=context.workspace_id,
                set_id=binding.space_id,
                rows=[
                    {
                        "id": object_id,
                        "kind": kind,
                        "content_hash": source_hash,
                        "embedding": vector,
                        "model": binding.embedder.model,
                    }
                ],
            )
