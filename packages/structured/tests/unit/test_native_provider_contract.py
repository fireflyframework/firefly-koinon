# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ServiceUnavailableException

from flyquery.config import FlyquerySettings
from flyquery.core.configuration import _use_redis
from flyquery.core.services.retrieval.embedder import FireflyEmbedder, build_embedder


def test_missing_embedding_prerequisite_cannot_silently_select_null_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ServiceUnavailableException, match="embedding provider"):
        build_embedder(FlyquerySettings(embedding_provider="openai"))


async def test_embedding_provider_failure_is_actionable_by_default():
    provider = SimpleNamespace(
        model="owned-model",
        embed_one=AsyncMock(side_effect=RuntimeError("offline")),
        embed=AsyncMock(side_effect=RuntimeError("offline")),
    )
    embedder = FireflyEmbedder(inner=provider, target_dim=128, native_dim=128)
    with pytest.raises(ServiceUnavailableException, match="embedding provider"):
        await embedder.embed("evidence")
    with pytest.raises(ServiceUnavailableException, match="embedding provider"):
        await embedder.embed_batch(["evidence"])


def test_persistent_agent_adapters_require_redis_unless_memory_is_explicit():
    with pytest.raises(RuntimeError, match="FLYQUERY_REDIS_URL"):
        _use_redis(FlyquerySettings(redis_url=""), "idempotency_backend")


def test_local_structured_agents_request_native_json_schema_output():
    from unittest.mock import MagicMock

    from pydantic_ai import NativeOutput

    from flyquery.core.agents.builder import build_agent
    from flyquery.core.agents.describe_agent import DescribedObjects

    factory = SimpleNamespace(create=MagicMock())
    settings = FlyquerySettings()
    settings.bind_agent_factory(factory)
    build_agent(
        name="describe",
        model="ollama:owned",
        output_type=DescribedObjects,
        instructions="Describe",
        settings=settings,
    )
    output = factory.create.call_args.kwargs["output_type"]
    assert isinstance(output, NativeOutput) and output.outputs is DescribedObjects
