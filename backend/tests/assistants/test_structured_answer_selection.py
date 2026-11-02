# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from flyquery.core.services.execution.duckdb_executor import ExecutionResult
from pydantic_ai.messages import RetryPromptPart, ToolReturnPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pyfly.agentic.models import ModelFactory
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.probe import ProviderProbe
from koinon.assistants.queue import AssistantQueue
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.capture_dtos import CapturedEvidence
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence


def capture(dataset, source, workspace, sql, rows, query_id):
    receipt = NativeEvidenceReceipt("issuer|admin", "north")
    identifier = receipt.sql_begin("direct", sql)
    receipt.sql_pins(identifier, {"products": "snapshot"})
    receipt.sql_tables(identifier, [{"table_id": "table", "name": "products", "snapshot_id": "snapshot"}])
    receipt.sql_engine(identifier, {"engine": "duckdb"}, executed=True)
    receipt.sql_classified(identifier, "SELECT")
    receipt.sql_executed(identifier, ExecutionResult(rows, list(rows[0]), len(rows), False))
    data = {
        "query_id": query_id,
        "execution_status": "OK",
        "sql": sql,
        "preview": rows,
        "row_count": len(rows),
        "truncated": False,
        "snapshot_pins": {"products": "snapshot"},
    }
    receipt.query("north", workspace, "issuer|admin", dataset, data)
    reference = SourceReference(
        id=query_id,
        asset_id=dataset,
        source_id=source,
        title="Products.xlsx",
        kind="dataset",
        snapshot_id="snapshot",
        used_revision="snapshot",
        query_id=query_id,
    )
    return CapturedEvidence(
        data,
        (reference,),
        receipt.complete,
        sql_attempts=receipt.sql_attempts,
        query_results=tuple(receipt.query_results),
    )


@pytest.mark.parametrize("repair", [True, False])
async def test_structured_results_repair_wrong_quote_kind_without_unverified_publication(
    assistants, monkeypatch, repair
):
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
    agent = await service.save_agent("issuer|admin", "north", {"tools": ["query_dataset"]}, agent["id"])
    parent = source = workspace = None
    for kind in ["workspace", "project", "collection", "source", "dataset"]:
        parent = await service.catalog.create(
            "issuer|admin", "north", kind=kind, name=kind, parent_id=parent.id if parent else None
        )
        if kind == "workspace":
            workspace = parent.id
        if kind == "source":
            source = parent.id
    total = capture(
        parent.id, source, workspace, "SELECT COUNT(*) AS total FROM products", [{"total": 12}], "total"
    )
    grouped = capture(
        parent.id,
        source,
        workspace,
        "SELECT category, COUNT(*) AS count FROM products GROUP BY category",
        [
            {"category": category, "count": count}
            for category, count in [("Widgets", 5), ("Accessories", 2), ("Bundles", 1), ("Gadgets", 4)]
        ],
        "grouped",
    )
    knowledge = SimpleNamespace(query=AsyncMock(side_effect=[total, grouped]))
    context.container.register_instance(NativeKnowledgeEvidence, knowledge)
    thread = await service.create_thread("issuer|admin", "north", {})
    await service.submit(
        "issuer|admin",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Cuenta los productos por categoría y el total. Responde en español.",
            "scope": {"asset_ids": [parent.id]},
            "client_request_id": "structured-selection",
        },
    )
    run = await context.get_bean(AssistantQueue).claim("structured-worker")
    attempts = 0

    async def streamed(messages, info):
        nonlocal attempts
        returns = [
            p
            for m in messages
            for p in m.parts
            if isinstance(p, ToolReturnPart) and p.tool_name == "query_dataset"
        ]
        if len(returns) < 2:
            yield {
                0: DeltaToolCall(
                    name="query_dataset",
                    json_args=json.dumps(
                        {"dataset_id": parent.id, "question": "total" if not returns else "by category"}
                    ),
                )
            }
            return
        facts = [f for item in returns for f in item.content["answer_facts"]]
        assert len(facts) == 9
        assert not (await service.message_repository.find_by_id(run.message_id)).text
        assert not any(
            e["type"] in {"message_delta", "citation", "openui_delta"}
            for e in await service.run_events("issuer|admin", "north", run.id)
        )
        attempts += 1
        if attempts > 1:
            feedback = " ".join(
                str(p.content) for m in messages for p in m.parts if isinstance(p, RetryPromptPart)
            )
            assert "QUOTE_NOT_RECORDED" in feedback
            assert "cell" in feedback and "derived" in feedback and "values" in feedback
            assert "strings" in feedback
        plan = {"outcome": "answer", "language": "es", "quotes": [{"fact_id": facts[0]["id"], "quote": "12"}]}
        if repair and attempts > 1:
            plan = {"outcome": "answer", "language": "es", "values": [{"fact_id": f["id"]} for f in facts]}
        yield {0: DeltaToolCall(name=info.output_tools[0].name, json_args=json.dumps(plan))}

    monkeypatch.setattr(
        ModelFactory, "build_with_secret", lambda self, spec, secret: FunctionModel(stream_function=streamed)
    )
    await context.get_bean(AssistantExecutor).execute(run.id, "structured-worker")
    message = await service.message_repository.find_by_id(run.message_id)
    assert message.status == "completed"
    assert attempts == 2 and knowledge.query.await_count == 2
    assert message.presentation["effective_language"] == "es"
    if repair:
        assert message.answer_policy["outcome"] == "grounded"
        assert message.text.startswith("El conocimiento seleccionado")
        assert "COUNT(products.*): 12" in message.text
        assert all(value in message.text for value in ("Widgets", "Accessories", "Bundles", "Gadgets"))
        assert {c["asset_id"] for c in message.citations} == {parent.id}
    else:
        assert message.answer_policy["code"] == "ANSWER_SELECTION_INVALID"
        assert "No se pudo verificar" in message.text and "Widgets" not in message.text
        assert message.citations == []
    assert message.answer_policy["validation"]["repairs"] == 1
    events = await service.run_events("issuer|admin", "north", run.id)
    assert "".join(e["data"]["text"] for e in events if e["type"] == "message_delta") == message.text
