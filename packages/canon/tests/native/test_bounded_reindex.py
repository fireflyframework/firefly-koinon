# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from flycanon.config import CanonSettings
from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetBinding, current_embedding_set
from flycanon.core.services.embeddings.reindex_service import ReindexError, ReindexService
from flycanon.web.conventions.context import TenantContext, set_tenant_context


@pytest.fixture
def scoped():
    token = set_tenant_context(TenantContext(tenant_id="tenant", workspace_id="workspace", actor="actor", correlation_id="test"))
    try:
        yield
    finally:
        token.var.reset(token.token)


def engine():
    binding = EmbeddingSetBinding("es-target", "ollama", "embedding", 768)
    chunks = SimpleNamespace(list_missing_for_set=AsyncMock(), count_for_workspace=AsyncMock(return_value=2), stamp_embedding_model=AsyncMock())
    embedder = SimpleNamespace(embed=AsyncMock(return_value=[[0.2] * 768]), strict=lambda: embedder)
    registry = SimpleNamespace(for_binding=lambda value: embedder)
    vectors = SimpleNamespace(upsert=AsyncMock())
    service = ReindexService(chunks=chunks, jobs=object(), sets=object(), registry=registry, vector_store=vectors, dense_backend=object(), settings=CanonSettings())
    return service, binding, chunks, embedder, vectors


async def test_bounded_step_rechecks_content_coverage_instead_of_model_stamp(scoped):
    service, binding, chunks, embedder, vectors = engine()
    chunk = SimpleNamespace(id="behind-cursor", content="edited same model", source_id="source", section_path=None, page=None)
    chunks.list_missing_for_set.side_effect = [[chunk], [chunk]]
    fence = AsyncMock()
    result = await service.step(tenant_id="tenant", workspace_id="workspace", binding=binding, batch_size=1, validate_write=fence)
    assert result["written"] == 1 and not result["complete"]
    assert chunks.list_missing_for_set.await_args.kwargs["limit"] == 1
    assert vectors.upsert.await_args.args[0][0].text == "edited same model"
    fence.assert_awaited_once()
    assert current_embedding_set() is None


async def test_bounded_step_cancellation_after_embedding_prevents_vector_commit(scoped):
    service, binding, chunks, embedder, vectors = engine()
    chunks.list_missing_for_set.return_value = [SimpleNamespace(id="chunk", content="text", source_id="source", section_path=None, page=None)]
    fence = AsyncMock(side_effect=ReindexError("Lease lost"))
    with pytest.raises(ReindexError):
        await service.step(tenant_id="tenant", workspace_id="workspace", binding=binding, validate_write=fence)
    embedder.embed.assert_awaited_once()
    vectors.upsert.assert_not_awaited()
    chunks.stamp_embedding_model.assert_not_awaited()


async def test_bounded_step_without_native_scope_refuses_before_repository_read():
    service, binding, chunks, _, _ = engine()
    with pytest.raises(ReindexError):
        await service.step(tenant_id="tenant", workspace_id="workspace", binding=binding)
    chunks.list_missing_for_set.assert_not_awaited()
