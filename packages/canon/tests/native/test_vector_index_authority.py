# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetBinding
from flycanon.core.services.retrieval.pgvector_store import RlsPgVectorVectorStore


async def test_existing_index_is_verified_without_issuing_owner_only_ddl():
    store = RlsPgVectorVectorStore(datasource=object(), dimension=128)
    connection = AsyncMock()
    connection.fetchval.return_value = True

    @asynccontextmanager
    async def operation(**kwargs):
        yield connection

    store._operation = operation
    assert await store.ensure_set_index(
        EmbeddingSetBinding(set_id="es-existing", provider="local", model="model", dimensions=128)
    )
    connection.execute.assert_not_awaited()


async def test_runtime_role_does_not_attempt_missing_index_ddl_or_poison_a_joined_transaction():
    store = RlsPgVectorVectorStore(datasource=object(), dimension=128)
    connection = AsyncMock()
    connection.fetchval.side_effect = [False, False]

    @asynccontextmanager
    async def operation(**kwargs):
        yield connection

    store._operation = operation
    assert not await store.ensure_set_index(
        EmbeddingSetBinding(set_id="es-new", provider="local", model="model", dimensions=128)
    )
    connection.execute.assert_not_awaited()
