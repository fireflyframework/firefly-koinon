# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Organization query policies remain local to the managed operation."""

from contextlib import asynccontextmanager

import flyquery.core.services.query.runtime as module
from flyquery.config import FlyquerySettings
from flyquery.data import StructuredSessionBinding


async def test_request_local_pipeline_uses_selected_limits_without_mutating_shared_resources(monkeypatch):
    built = []

    def agent(settings):
        built.append(settings)
        return object()

    for name in (
        "build_grounding_agent",
        "build_generation_agent",
        "build_critic_agent",
        "build_explainer_agent",
    ):
        monkeypatch.setattr(module, name, agent)

    @asynccontextmanager
    async def session():
        yield object()

    baseline = FlyquerySettings(max_refine_retries=2, rrf_k=60)
    factory = module.StructuredQueryRuntimeFactory(
        settings=baseline,
        sessions=StructuredSessionBinding(session),
        object_store=object(),
        query_repository=object(),
        semantic_repository=object(),
        examples_service=object(),
        embedder=object(),
        reranker=object(),
        ast_classifier=object(),
        scope_guard=object(),
        executor=object(),
        table_repository=object(),
        conversation_service=object(),
    )
    async with factory.unit(
        settings_overrides={
            "max_refine_retries": 0,
            "rrf_k": 91,
            "top_k_schema": 7,
            "generation_candidates": 1,
            "grounding_min_confidence": 0.7,
        }
    ) as first:
        assert built and all(settings is first.settings for settings in built)
        assert first.pipeline._settings is first.settings and first.critic_agent is None
        assert first.settings.top_k_schema == 7 and first.settings.generation_candidates == 1
        assert first.settings.grounding_min_confidence == 0.7 and first.settings.rrf_k == 91
        assert first.pipeline._executor is factory._executor
        assert first.pipeline._scope_guard is factory._scope_guard
    built.clear()
    async with factory.unit() as second:
        assert all(settings is baseline for settings in built)
        assert second.settings is baseline and second.critic_agent is not None
    assert baseline.rrf_k == 60 and baseline.max_refine_retries == 2
