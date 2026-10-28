# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock

from pydantic_ai.models.test import TestModel
from pyfly.agentic.models import ModelFactory
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.probe import ProviderProbe
from koinon.assistants.queue import AssistantQueue


def test_model_evidence_budget_preserves_exact_cells_and_exposes_omitted_records():
    import json

    from koinon.assistants.grounding import evidence_view, has_evidence

    raw = {
        "execution_status": "OK",
        "preview": [{"amount": "18446744073709551615", "flag": False}, {"large": "x" * 2000}],
        "row_count": 2,
    }
    view = evidence_view("query", raw, "evidence", 512)
    assert view["preview"] == [raw["preview"][0]] and view["truncated"] is True
    assert len(json.dumps(view).encode()) < 512 and has_evidence("query", view)
    assert len(raw["preview"]) == 2
    assert not has_evidence("search", evidence_view("search", {"hits": []}, "empty", 128))
    assert not has_evidence("query", {"execution_status": "OK", "preview": [], "row_count": False})


async def test_unrelated_model_answer_never_reaches_durable_text_or_stream(assistants, monkeypatch):
    service, context = assistants
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[
                {"id": "connection", "status": "passed", "message": "Controlled"},
                {"id": "models", "status": "passed", "message": "Discovered"},
            ]
        ),
    )
    provider, agent = await configured(service)
    await service.validate_provider("issuer|admin", "north", provider["id"])
    model = TestModel(
        call_tools=[], custom_output_text="Invented unrelated answer that must never be published."
    )
    monkeypatch.setattr(ModelFactory, "build_with_secret", lambda self, spec, secret: model)
    thread = await service.create_thread("issuer|viewer", "north", {})
    submitted = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Write an unrelated poem.",
            "client_request_id": "refusal-proof",
        },
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("policy-worker")
    await context.get_bean(AssistantExecutor).execute(run.id, "policy-worker")
    answer = (await service.messages("issuer|viewer", "north", thread["id"]))[-1]
    assert answer["status"] == "completed"
    assert "Invented unrelated" not in answer["text"]
    assert answer["answer_policy"]["outcome"] == "refused"
    assert answer["answer_policy"]["code"] == "KNOWLEDGE_ONLY"
    events = await service.run_events("issuer|viewer", "north", submitted["run_id"])
    assert all("Invented unrelated" not in str(event["data"]) for event in events)
    assert any(
        event["type"] == "message_metadata"
        and event["data"].get("answer_policy", {}).get("outcome") == "refused"
        for event in events
    )
