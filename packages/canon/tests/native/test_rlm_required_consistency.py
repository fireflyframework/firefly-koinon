# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Required selection admission; candidate execution is an explicit local seam."""

import json
from contextlib import contextmanager
from hashlib import sha256
from itertools import count
from threading import current_thread
from types import SimpleNamespace

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from pyfly.kernel import ServiceUnavailableException

from flycanon.config import CanonSettings
from flycanon.core.agents.model_bindings import ModelBinding, push_bindings, reset_bindings
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.corpus import SourceMeta
from flycanon.core.services.query.rlm_answer_service import RLMAnswerService
from flycanon.core.services.sources.lineage.dtos import DocumentCitationRef
from flycanon.interfaces.dtos.query import AnswerRequest
from flycanon.web.conventions.context import TenantContext, set_tenant_context


class Corpus:
    def __len__(self):
        return 1

    def __iter__(self):
        return iter(["A"])

    def resolve(self, key):
        return SourceMeta(
            source_id="source",
            filename="source.txt",
            title=None,
            kind="text",
            object_store_key="fixture",
            content_sha256="a" * 64,
            tenant_id="fixture",
            workspace_id="workspace",
            source_version_id="fixture-version",
            ingestion_extraction_id="fixture-extraction",
        )

    def citation_ref(self, key, page, content):
        text = "first second"
        if key != "A" or page != 0 or content not in text:
            return None
        return DocumentCitationRef(
            "source",
            "fixture-version",
            "fixture-extraction",
            "fixture-part",
            sha256(text.encode()).hexdigest(),
            None,
            "recorded_loader",
        )


class Builder:
    async def build(self, **kwargs):
        return Corpus()


class Cost:
    def __init__(self):
        self.calls = []

    async def record(self, **kwargs):
        self.calls.append(kwargs)


class Observer:
    def __init__(self):
        self.records = []
        self.revoked = False

    async def authorize(self):
        if self.revoked:
            raise ServiceUnavailableException("Evidence authorization ended", code="SCOPE_REVOKED")

    def document_origin(self, *args):
        pass

    def document_sync(self, stage, content, source_ids, scope):
        assert provenance.current() is scope
        self.records.append((stage, content, current_thread(), sha256(content.encode()).hexdigest()))


@contextmanager
def required(observer, model=None, output_mode="default"):
    context = set_tenant_context(
        TenantContext(
            tenant_id="fixture",
            workspace_id="workspace",
            actor="owner",
            correlation_id="consistency",
        )
    )
    model = model or FunctionModel(lambda messages, info: ModelResponse(parts=[TextPart("1")]))
    token = push_bindings(
        tenant_id="fixture",
        workspace_id="workspace",
        subject="owner",
        bindings={
            "documents.rlm": ModelBinding(
                model,
                {"max_tokens": 64},
                "ollama",
                "chat",
                output_mode=output_mode,
            )
        },
    )
    try:
        with provenance.observe(observer, tenant_id="fixture", workspace_id="workspace", actor="owner"):
            yield token.scope
    finally:
        reset_bindings(token)
        context.var.reset(context.token)


class Selector:
    def __init__(self, reply="2", error=None, on_complete=None):
        self.reply, self.error, self.on_complete = reply, error, on_complete
        self.calls = 0
        self.thread = None

    def complete(self, prompt):
        self.calls += 1
        self.thread = current_thread()
        if self.on_complete:
            self.on_complete()
        if self.error:
            raise self.error
        return self.reply

    def token_totals(self):
        return dict(input_tokens=5, output_tokens=2, estimated_cost_usd=0.0, by_model={})


def service(monkeypatch, candidates, selector=None, *, citations=True):
    settings = CanonSettings(rlm_self_consistency=len(candidates))
    cost = Cost()
    result = RLMAnswerService(
        corpus_builder=Builder(), client=SimpleNamespace(), settings=settings, cost_service=cost
    )
    ordinal = count()

    def candidate(*args):
        assert args[-1] is not None  # Keep the source6 metadata context.
        value = candidates[next(ordinal)]
        if isinstance(value, BaseException):
            raise value
        references = [{"filing": "A", "page": 0, "content": value}] if citations else []
        return (
            value,
            references,
            False,
            dict(input_tokens=2, output_tokens=1, estimated_cost_usd=0.0, by_model={}),
        )

    monkeypatch.setattr(result, "_run_once", candidate)
    if selector is not None:
        monkeypatch.setattr(result, "_request_client", lambda: selector)
    return result, cost


async def answer(service):
    return await service.answer(
        AnswerRequest(question="Inspect the source"), tenant_id="fixture", workspace_id="workspace"
    )


@pytest.mark.parametrize("partial", [False, True])
async def test_required_candidates_propagate_any_execution_failure(monkeypatch, partial):
    error = ServiceUnavailableException("Secure execution ended", code="RLM_SECURE_EXECUTION_REQUIRED")
    selector = Selector()
    instance, cost = service(monkeypatch, [error, "second" if partial else error], selector)
    with required(Observer()), pytest.raises(ServiceUnavailableException) as raised:
        await answer(instance)
    assert raised.value is error and selector.calls == 0 and cost.calls == []


async def test_required_selected_answer_without_citations_fails_before_cost(monkeypatch):
    instance, cost = service(monkeypatch, ["first", "second"], Selector(), citations=False)
    with required(Observer()), pytest.raises(ServiceUnavailableException) as raised:
        await answer(instance)
    assert raised.value.code == "EVIDENCE_UNAVAILABLE" and cost.calls == []


async def test_required_selector_runs_on_an_authorized_worker_and_merges_actual_spend(monkeypatch):
    observer, selector = Observer(), Selector()
    instance, cost = service(monkeypatch, ["first", "second"], selector)
    owner = current_thread()
    with required(observer):
        result = await answer(instance)
    assert result.answer == "Source excerpts\n\nSource excerpt 1:\n> second"
    assert [hit.content for hit in result.citations] == ["second"]
    assert selector.thread is not owner
    stage = [row for row in observer.records if row[0] == "rlm.selector"]
    assert len(stage) == 1 and stage[0][2] is selector.thread
    assert cost.calls[0]["input_tokens"] == 9 and cost.calls[0]["output_tokens"] == 4


@pytest.mark.parametrize("reply", ["pick 2", "2 extra", "1 2", "0", "3", "01", "", "NaN", None, 2, True])
async def test_required_selector_rejects_nonexact_or_out_of_range_choices(monkeypatch, reply):
    instance, cost = service(monkeypatch, ["first", "second"], Selector(reply))
    with required(Observer()), pytest.raises(ServiceUnavailableException) as raised:
        await answer(instance)
    assert raised.value.code == "RLM_SELECTOR_PROTOCOL_REQUIRED" and cost.calls == []


async def test_required_selector_preserves_provider_failure(monkeypatch):
    error = ServiceUnavailableException("Provider ended", code="RLM_PROVIDER_UNAVAILABLE")
    instance, cost = service(monkeypatch, ["first", "second"], Selector(error=error))
    with required(Observer()), pytest.raises(ServiceUnavailableException) as raised:
        await answer(instance)
    assert raised.value is error and cost.calls == []


async def test_required_selector_rechecks_authority_after_completion(monkeypatch):
    observer = Observer()
    selector = Selector(on_complete=lambda: setattr(observer, "revoked", True))
    instance, cost = service(monkeypatch, ["first", "second"], selector)
    with required(observer), pytest.raises(ServiceUnavailableException) as raised:
        await answer(instance)
    assert raised.value.code == "SCOPE_REVOKED" and selector.calls == 1 and cost.calls == []


async def test_required_selector_worker_rechecks_authority_before_dispatch(monkeypatch):
    class RevokeBeforeWorker(Observer):
        calls = 0

        async def authorize(self):
            await super().authorize()
            self.calls += 1
            if self.calls == 2:  # Corpus admission and async pre-selection admission succeeded.
                self.revoked = True

    observer, selector = RevokeBeforeWorker(), Selector()
    instance, cost = service(monkeypatch, ["first", "second"], selector)
    with required(observer), pytest.raises(ServiceUnavailableException) as raised:
        await answer(instance)
    assert raised.value.code == "SCOPE_REVOKED" and selector.calls == 0 and cost.calls == []


async def test_required_selection_cannot_outlive_its_borrowed_binding(monkeypatch):
    selector = Selector()
    instance, cost = service(monkeypatch, ["first", "second"], selector)
    with required(Observer()) as scope, pytest.raises(ServiceUnavailableException) as raised:
        selector.on_complete = lambda: setattr(scope, "closed", True)
        await answer(instance)
    assert raised.value.code == "KNOWLEDGE_MODEL_SCOPE_CLOSED" and cost.calls == []


@pytest.mark.timeout(10)
@pytest.mark.parametrize("output_mode", ["native", "default"])
async def test_required_selector_uses_actual_native_client_sdk_wire_and_ledger(monkeypatch, output_mode):
    import httpx2
    from pyfly.agentic.factory import AgentFactory
    from pyfly.agentic.models import Credential, ModelFactory, ModelOptions, ModelSpec
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    observed = []

    def respond(request):
        observed.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "offline-selector",
                "object": "chat.completion",
                "created": 0,
                "model": "qualified-selector",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "2"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        )

    monkeypatch.setattr(
        "pydantic_ai.providers._openai_compatible.create_async_httpx2_client",
        lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(respond), trust_env=False),
    )
    model = await ModelFactory().build(
        ModelSpec(
            provider="ollama",
            model="qualified-selector",
            model_class="OpenAIChatModel",
            base_url="http://127.0.0.1:11434/v1",
            credential=Credential.none(),
            options=ModelOptions(max_tokens=64),
        )
    )
    app = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "agentic": {"enabled": True},
                    "eda": {"provider": "memory"},
                }
            }
        )
    )
    await app.start()
    instance, cost = service(monkeypatch, ["first", "second"])
    instance._settings._agent_factory = app.get_bean(AgentFactory)
    observer = Observer()
    try:
        with required(observer, model, output_mode):
            result = await answer(instance)
        assert result.answer == "Source excerpts\n\nSource excerpt 1:\n> second"
        assert [hit.content for hit in result.citations] == ["second"]
        assert len(observed) == 1
        wire = observed[0]
        assert wire["max_tokens"] == 64 and "max_completion_tokens" not in wire
        assert not wire.get("tools") and "tool_choice" not in wire
        selector_stage = [row for row in observer.records if row[0] == "rlm.selector"]
        assert len(selector_stage) == 1 and selector_stage[0][2] is not current_thread()
        assert selector_stage[0][1] == wire["messages"][-1]["content"]
        assert selector_stage[0][3] == sha256(wire["messages"][-1]["content"].encode()).hexdigest()
        assert cost.calls[0]["input_tokens"] == 9 and cost.calls[0]["output_tokens"] == 4
    finally:
        await app.stop()
