# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Different organization budgets must not change the controller template."""

import flyquery.web.controllers.query_controller as module
from flyquery.config import FlyquerySettings


def test_request_local_pipeline_uses_selected_limits_without_mutating_shared_resources(monkeypatch):
    built = []

    def agent(settings):
        built.append(settings)
        return object()

    for name in (
        "build_grounding_agent",
        "build_generation_agent",
        "build_critic_agent",
        "build_explainer_agent",
        "build_reranker",
    ):
        monkeypatch.setattr(module, name, agent)
    controller = object.__new__(module.QueryController)
    baseline = FlyquerySettings(max_refine_retries=2, rrf_k=60)
    controller._settings = baseline
    for name in (
        "_embedder",
        "_object_store",
        "_query_repo",
        "_examples_service",
        "_ast_classifier",
        "_scope_guard",
        "_executor",
        "_semantic_repo",
    ):
        setattr(controller, name, object())
    selected = baseline.model_copy(
        update={
            "max_refine_retries": 0,
            "rrf_k": 91,
            "top_k_schema": 7,
            "generation_candidates": 1,
            "grounding_min_confidence": 0.7,
        }
    )
    first = controller._build_service(None, settings=selected)
    assert built and all(settings is selected for settings in built)
    assert first._settings is selected and first._critic_agent is None
    assert first._settings.top_k_schema == 7 and first._settings.generation_candidates == 1
    assert first._settings.grounding_min_confidence == 0.7
    assert first._executor is controller._executor
    assert first._scope_guard is controller._scope_guard
    built.clear()
    second = controller._build_service(None)
    assert all(settings is baseline for settings in built)
    assert second._settings is baseline and second._critic_agent is not None
    assert baseline.rrf_k == 60 and baseline.max_refine_retries == 2
    assert first._settings.rrf_k == 91
