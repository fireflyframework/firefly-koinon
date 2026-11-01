# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pyfly.agentic.models import ModelFactory
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.probe import ProviderProbe
from koinon.assistants.queue import AssistantQueue
from koinon.catalog.service import CatalogService
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.capture_dtos import CapturedEvidence
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence


@pytest.mark.parametrize(
    "case", ["valid", "raw_draft", "forged_id", "mixed", "forged_quote", "free_prose", "empty"]
)
async def test_real_executor_releases_only_valid_current_source_plan(assistants, monkeypatch, case):
    service, context = assistants
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[{"id": "connection", "status": "passed"}, {"id": "models", "status": "passed"}]
        ),
    )
    provider, agent = await configured(service)
    await service.validate_provider("issuer|admin", "north", provider["id"])
    parent = source = None
    for kind in ["workspace", "project", "collection", "source", "document"]:
        parent = await context.get_bean(CatalogService).create(
            "issuer|admin",
            "north",
            kind=kind,
            name="Controlled " + kind,
            parent_id=parent.id if parent else None,
        )
        if kind == "source":
            source = parent
    passage = "The approved maintenance window is Tuesday at 09:00 UTC."
    reference = SourceReference(
        id="native-proof",
        asset_id=parent.id,
        source_id=source.id,
        title="Maintenance window",
        kind="document",
        chunk_id="chunk",
        quote=passage,
        used_revision="chunk-sha256:" + sha256(passage.encode()).hexdigest(),
    )
    data = {
        "hits": []
        if case == "empty"
        else [{"asset_id": parent.id, "id": "chunk", "title": "Maintenance window", "text": passage}]
    }
    knowledge = SimpleNamespace(
        search=AsyncMock(return_value=CapturedEvidence(data, () if case == "empty" else (reference,), True))
    )
    context.container.register_instance(NativeKnowledgeEvidence, knowledge)
    thread = await service.create_thread("issuer|viewer", "north", {})
    await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "When is the maintenance window?",
            "scope": {"asset_ids": [parent.id]},
            "client_request_id": case,
        },
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("knowledge-only")

    async def streamed(messages, info):
        returns = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart) and part.tool_name == "search_knowledge"
        ]
        if not returns:
            yield {
                0: DeltaToolCall(
                    name="search_knowledge", json_args=json.dumps({"question": "maintenance window"})
                )
            }
            return
        # Even after successful retrieval, there is no durable or replayable draft answer.
        assert not (await service.message_repository.find_by_id(run.message_id)).text
        events = await service.run_events("issuer|viewer", "north", run.id)
        assert not any(item["type"] in {"message_delta", "openui_delta", "citation"} for item in events)
        facts = returns[-1].content.get("answer_facts", [])
        if case == "raw_draft":
            yield "UNSUPPORTED_TRAINING_FACT: Jupiter has 999 moons."
            return
        selection = {"fact_id": facts[0]["id"] if facts else "missing", "quote": passage}
        plan = {"outcome": "answer", "quotes": [selection], "values": []}
        if case == "forged_id":
            selection["fact_id"] = "forged-source"
        if case == "mixed":
            plan["quotes"].append({"fact_id": "invented", "quote": "UNSUPPORTED_TRAINING_FACT"})
        if case == "forged_quote":
            selection["quote"] = "UNSUPPORTED_TRAINING_FACT: Jupiter has 999 moons."
        if case == "free_prose":
            plan["answer"] = "UNSUPPORTED_TRAINING_FACT"
        yield {0: DeltaToolCall(name=info.output_tools[0].name, json_args=json.dumps(plan))}

    monkeypatch.setattr(
        ModelFactory, "build_with_secret", lambda self, spec, secret: FunctionModel(stream_function=streamed)
    )
    await context.get_bean(AssistantExecutor).execute(run.id, "knowledge-only")
    message = await service.message_repository.find_by_id(run.message_id)
    assert message.status == "completed", (await service.runs.find_by_id(run.id)).error_code
    assert knowledge.search.await_count == 1
    assert "UNSUPPORTED_TRAINING_FACT" not in message.text
    assert message.answer_policy["outcome"] == ("grounded" if case == "valid" else "refused")
    assert (passage in message.text) is (case == "valid")
    events = await service.run_events("issuer|viewer", "north", run.id)
    assert [item["data"]["text"] for item in events if item["type"] == "message_delta"] == [message.text]
    assert "UNSUPPORTED_TRAINING_FACT" not in str(events)
    assert (
        len([row for row in await service.results.find_all(run_id=run.id) if row.kind == "answer_release"])
        == 1
    )
