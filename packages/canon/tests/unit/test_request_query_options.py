# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Request-local configuration must not change another tenant's answer engine."""
import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from flycanon.config import CanonSettings
from flycanon.core.services.query.answer_dispatcher import AnswerDispatcher
from flycanon.core.services.query.runtime import DocumentQueryOptions, scoped_answer, scoped_search
from flycanon.core.services.query.search_service import SearchService
from flycanon.core.services.retrieval.retrieval_service import RetrievalService
from flycanon.interfaces.dtos.query import AnswerRequest


def options(**changes):
    return DocumentQueryOptions(**{
        "answer_mode": "rag", "retrieval_top_k": 10, "retrieval_per_query_k": 30,
        "retrieval_rrf_k": 60, "query_expansion_enabled": False, "query_expansion_n": 3,
        "answer_top_k": 10, "rlm_max_iters": 8, "rlm_sub_budget": 12,
        "rlm_max_depth": 1, "rlm_self_consistency": 1, "rlm_extended_reasoning": False,
        **changes,
    })


def retrieval():
    return RetrievalService(context=object(), embeddings=object(), source_repository=object(),
                            chunk_repository=object(), knowledge_repository=object(),
                            default_top_k=10, default_per_query_k=30, rrf_k=60)


@pytest.mark.parametrize("change", [
    {"answer_mode": "unknown"}, {"rlm_max_iters": True}, {"rlm_sub_budget": -1},
    {"rlm_max_depth": 9}, {"rlm_extended_reasoning": "true"}, {"provider_url": "invalid"},
])
def test_runtime_options_reject_unbounded_or_unapproved_configuration(change):
    with pytest.raises(ValidationError):
        options(**change)


def test_search_parameters_are_copied_without_mutating_the_shared_retrieval():
    shared = SearchService(retrieval=retrieval())
    baseline = CanonSettings(query_expansion_enabled=False)
    selected = scoped_search(shared, baseline, options(retrieval_top_k=42, retrieval_per_query_k=73,
                                                      retrieval_rrf_k=91))
    assert selected is not shared and selected._retrieval is not shared._retrieval
    assert (selected._retrieval._default_top_k, selected._retrieval._default_per_query_k,
            selected._retrieval._rrf_k) == (42, 73, 91)
    assert (shared._retrieval._default_top_k, shared._retrieval._default_per_query_k,
            shared._retrieval._rrf_k) == (10, 30, 60)
    assert selected._retrieval._context is shared._retrieval._context
    assert selected._retrieval._source_repo is shared._retrieval._source_repo


def test_query_expansion_is_request_local_and_preserves_deployment_model_resources():
    baseline = CanonSettings(query_expansion_enabled=False)
    shared = SearchService(retrieval=retrieval())
    selected = scoped_search(shared, baseline, options(query_expansion_enabled=True,
                                                      query_expansion_n=7))
    assert shared._retrieval._query_expander is None
    assert selected._retrieval._query_expander is not None
    assert selected._retrieval._query_expansion_n == 7
    assert selected._retrieval._query_expander._settings.query_expansion_enabled is True
    assert baseline.query_expansion_enabled is False


class AnswerSpy:
    def __init__(self, settings, reads):
        self._settings, self._retrieval = settings, reads

    async def answer(self, request, **scope):
        await asyncio.sleep(0)
        return SimpleNamespace(mode=self._settings.answer_mode, steps=self._settings.rlm_max_iters,
                               scope=scope, source_ids=request.source_ids)


@pytest.mark.asyncio
async def test_concurrent_answer_dispatchers_keep_each_organizations_mode_and_budget():
    baseline = CanonSettings(answer_mode="rlm", rlm_max_iters=8)
    reads = retrieval()
    shared = AnswerDispatcher(AnswerSpy(baseline, reads), AnswerSpy(baseline, reads), baseline)
    rag = scoped_answer(shared, options(answer_mode="rag", rlm_max_iters=3))
    rlm = scoped_answer(shared, options(answer_mode="rlm", rlm_max_iters=11))
    request = AnswerRequest(question="What is recorded?", source_ids=["approved-source"])
    first, second = await asyncio.gather(
        rag.answer(request, tenant_id="organization-a", workspace_id="workspace-a"),
        rlm.answer(request, tenant_id="organization-b", workspace_id="workspace-b"),
    )
    assert (first.mode, first.steps, first.scope["tenant_id"]) == ("rag", 3, "organization-a")
    assert (second.mode, second.steps, second.scope["tenant_id"]) == ("rlm", 11, "organization-b")
    assert first.source_ids == second.source_ids == ["approved-source"]
    assert shared.mode == "rlm" and baseline.rlm_max_iters == 8
    assert rag._rag is not shared._rag and rlm._rlm is not shared._rlm
    assert rag._rag._retrieval is not reads


def test_runtime_settings_do_not_include_answer_only_fields_or_change_sandbox():
    baseline = CanonSettings(rlm_sandbox="subprocess")
    effective = options(rlm_max_iters=5, rlm_extended_reasoning=True).settings(baseline)
    assert effective is not baseline and effective.rlm_max_iters == 5
    assert effective.rlm_sandbox == baseline.rlm_sandbox == "subprocess"
    assert not hasattr(effective, "answer_top_k")
    assert not hasattr(effective, "rlm_extended_reasoning")


def test_runtime_settings_preserve_bound_private_resources_without_rebinding_shared_settings():
    baseline = CanonSettings(query_expansion_enabled=False)
    factory, registry = object(), object()
    baseline._agent_factory = factory
    baseline._datasource_registry = registry
    baseline._require_model_bindings = True

    selected = options(rlm_max_iters=5, query_expansion_enabled=True).settings(baseline)

    assert selected is not baseline
    assert selected._agent_factory is factory
    assert selected._datasource_registry is registry
    assert selected._require_model_bindings is True
    assert (selected.rlm_max_iters, selected.query_expansion_enabled) == (5, True)
    assert (baseline.rlm_max_iters, baseline.query_expansion_enabled) == (8, False)
    assert baseline._agent_factory is factory and baseline._datasource_registry is registry


@pytest.mark.asyncio
async def test_scoped_rlm_services_fork_real_native_clients_with_independent_usage_ledgers():
    from flycanon.core.services.query.rlm.native_client import NativeRlmChatClient
    from flycanon.core.services.query.rlm_answer_service import RLMAnswerService

    settings = CanonSettings(rlm_root_model="ollama:local-test", rlm_sub_model="ollama:local-test")
    factory = SimpleNamespace(create=lambda *args, **kwargs: object())
    template = NativeRlmChatClient(settings, factory)
    reads = retrieval()
    rlm = RLMAnswerService(corpus_builder=object(), client=template, settings=settings,
                           cost_service=object())
    shared = AnswerDispatcher(AnswerSpy(settings, reads), rlm, settings)
    first = scoped_answer(shared, options(answer_mode="rlm", rlm_max_iters=3))
    second = scoped_answer(shared, options(answer_mode="rlm", rlm_max_iters=11))

    first_client, second_client = first._rlm._request_client(), second._rlm._request_client()
    assert isinstance(first_client, NativeRlmChatClient)
    assert isinstance(second_client, NativeRlmChatClient)
    assert first_client is not second_client and first_client is not template
    first_client._ledger.record("local-test", input_tokens=13, output_tokens=7)
    second_client._ledger.record("local-test", input_tokens=2, output_tokens=3)

    assert (first_client.token_totals()["input_tokens"], first_client.token_totals()["output_tokens"]) == (13, 7)
    assert (second_client.token_totals()["input_tokens"], second_client.token_totals()["output_tokens"]) == (2, 3)
    assert template.token_totals()["input_tokens"] == template.token_totals()["output_tokens"] == 0
    first_client.reset_tokens()
    assert first_client.token_totals()["input_tokens"] == 0
    assert second_client.token_totals()["input_tokens"] == 2
    assert (first._rlm._settings.rlm_max_iters, second._rlm._settings.rlm_max_iters,
            shared._rlm._settings.rlm_max_iters) == (3, 11, 8)
