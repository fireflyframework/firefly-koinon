# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from flyquery.core.services.retrieval.versioned_index import VersionedIndexService, content_hash


def test_index_content_identity_covers_model_independent_text_and_example_sql():
    assert content_hash("same text") == content_hash("same text")
    assert content_hash("same text") != content_hash("edited text")
    assert len(content_hash("evidence")) == 64


async def test_versioned_step_reuses_original_schema_text_and_fences_before_write():
    row = {
        "id": uuid4(),
        "kind": "schema",
        "qualified_name": "amount",
        "data_type": "INTEGER",
        "description": "Total",
        "synonyms_json": None,
        "sample_values_json": [],
        "profile_json": {"top_values": [{"value": "secret"}]},
    }
    repo = SimpleNamespace(
        missing=AsyncMock(side_effect=[[row], []]),
        upsert=AsyncMock(),
        counts=AsyncMock(return_value={"chunk_count": 1, "vector_count": 1}),
    )
    service = VersionedIndexService(repo)
    embedder = SimpleNamespace(embed=AsyncMock(return_value=SimpleNamespace(embeddings=[[0.1] * 768])))
    fence = AsyncMock()
    result = await service.step(
        tenant_id="tenant",
        workspace_id=str(uuid4()),
        set_id="set",
        embedder=embedder,
        dimensions=768,
        model="embedding",
        batch_size=1,
        validate_write=fence,
    )
    text = embedder.embed.await_args.args[0][0]
    assert "amount: INTEGER" in text and "secret" not in text
    fence.assert_awaited_once()
    vector = repo.upsert.await_args.kwargs["rows"][0]
    assert len(vector["embedding"]) == 1536 and vector["embedding"][768:] == [0.0] * 768
    assert result["complete"] and result["written"] == 1


async def test_versioned_step_does_not_overwrite_original_or_commit_after_cancel():
    repo = SimpleNamespace(
        missing=AsyncMock(
            return_value=[
                {"id": uuid4(), "kind": "example", "question": "What?", "generated_sql": "SELECT 12"}
            ]
        ),
        upsert=AsyncMock(),
    )
    embedder = SimpleNamespace(embed=AsyncMock(return_value=SimpleNamespace(embeddings=[[0.1] * 768])))
    fence = AsyncMock(side_effect=RuntimeError("cancelled"))
    with pytest.raises(RuntimeError, match="cancelled"):
        await VersionedIndexService(repo).step(
            tenant_id="tenant",
            workspace_id=str(uuid4()),
            set_id="set",
            embedder=embedder,
            dimensions=768,
            model="embedding",
            validate_write=fence,
        )
    repo.upsert.assert_not_awaited()
    assert embedder.embed.await_args.args[0] == ["What?"]


async def test_versioned_native_binding_replaces_only_request_embedding_profile():
    from flyquery.core.agents.model_bindings import EmbeddingBinding, push_bindings, reset_bindings
    from flyquery.core.services.retrieval.embedder import FireflyEmbedder
    from flyquery.web.conventions.context import TenantContext, set_tenant_context

    context = set_tenant_context(
        TenantContext(tenant_id="tenant", workspace_id=str(uuid4()), actor="actor", correlation_id="test")
    )
    from flyquery.web.conventions.context import current_tenant_context

    workspace_id = current_tenant_context().workspace_id
    inner = SimpleNamespace(model="selected", dimensions=768, embed_one=AsyncMock(return_value=[0.2] * 768))
    token = push_bindings(
        tenant_id="tenant",
        workspace_id=str(workspace_id),
        subject="actor",
        bindings={},
        embeddings={
            "structured.embedding": EmbeddingBinding(
                inner, "ollama:selected", 768, 1536, "fs-" + "a" * 32, versioned=True
            )
        },
    )
    service = FireflyEmbedder(
        inner=None,
        target_dim=1536,
        native_dim=1536,
        embedding_model="openai:deployment",
        space_id="deployment",
    )
    try:
        assert service.model == "selected"
        assert len(await service.embed("question")) == 1536
        assert service._native_dim == 1536 and service._embedding_model == "openai:deployment"
    finally:
        reset_bindings(token)
        context.var.reset(context.token)
