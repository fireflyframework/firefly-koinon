# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pyfly.agentic.models import ModelFactory
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.probe import ProviderProbe
from koinon.assistants.queue import AssistantQueue
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.evidence_capture import CapturedEvidence, NativeKnowledgeEvidence


def test_schema_and_empty_results_never_establish_factual_grounding():
    from koinon.assistants.grounding import has_evidence

    assert not has_evidence("schema", {"tables": [{"name": "schema-only"}]})
    assert not has_evidence("query", {"execution_status": "OK", "preview": [], "row_count": 0})
    assert not has_evidence("search", {"hits": [{"text": ""}]})


@pytest.mark.parametrize(
    "case",
    [
        "incomplete",
        "schema",
        "empty_query",
        "empty_search",
        "proposal",
        "native_unavailable",
        "native_denied",
    ],
)
async def test_native_worker_blocks_unprovenanced_data_and_publishes_honest_policy(
    assistants, monkeypatch, case
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
    tool = {
        "incomplete": "search_knowledge",
        "schema": "inspect_schema",
        "empty_query": "query_dataset",
        "empty_search": "search_knowledge",
        "proposal": "propose_catalog_update",
        "native_unavailable": "search_knowledge",
        "native_denied": "search_knowledge",
    }[case]
    agent = await service.save_agent("issuer|admin", "north", {"tools": [tool]}, agent["id"])
    parent = None
    kind = "document" if tool == "search_knowledge" else "dataset"
    for entry_kind in ("workspace", "project", "collection", "source", kind):
        parent = await service.catalog.create(
            "issuer|admin", "north", kind=entry_kind, name=entry_kind, parent_id=parent.id if parent else None
        )
    asset = parent
    source = SourceReference(
        id="captured",
        asset_id=asset.id,
        source_id=asset.parent_id,
        title=asset.name,
        kind=kind,
        used_revision="snapshot-used",
    )
    if case == "incomplete":
        data = {
            "hits": [
                {
                    "id": "chunk",
                    "asset_id": asset.id,
                    "source_id": asset.parent_id,
                    "title": "Document",
                    "text": "BLOCKED_CONTENT_4892",
                }
            ]
        }
    elif case == "schema":
        data = {
            "tables": [
                {
                    "id": "table",
                    "name": "Facts",
                    "columns": [{"id": "column", "name": "amount", "data_type": "INTEGER"}],
                }
            ]
        }
    elif case == "empty_query":
        data = {"query_id": "query", "execution_status": "OK", "row_count": 0, "preview": []}
    else:
        data = {"hits": []}
    capture = CapturedEvidence(
        data, () if case in {"incomplete", "empty_search"} else (source,), case != "incomplete"
    )
    methods = type("ControlledNativeRead", (), {})()
    method = "search" if tool == "search_knowledge" else "schema" if tool == "inspect_schema" else "query"
    setattr(methods, method, AsyncMock(return_value=capture))
    if case == "native_unavailable":
        from pyfly.kernel import ServiceUnavailableException

        getattr(methods, method).side_effect = ServiceUnavailableException(
            "Native schema provenance is missing", code="EVIDENCE_UNAVAILABLE"
        )
    if case == "native_denied":
        from koinon.knowledge.capture_dtos import NativeReadFingerprint
        from koinon.knowledge.evidence_capture import NativeEvidenceDenied

        async def denied(*args, **kwargs):
            member = await service.catalog.membership_repository.find_by_id("admin")
            member.active = False
            await service.catalog.membership_repository.save(member)
            failure = NativeEvidenceDenied("Source access changed", code="EVIDENCE_UNAVAILABLE")
            failure.capture = CapturedEvidence(
                {},
                (source,),
                False,
                (
                    NativeReadFingerprint(
                        "grounding",
                        "documents",
                        "north",
                        asset.workspace_id,
                        asset.id,
                        "a" * 64,
                        ("native-source",),
                        (),
                    ),
                ),
            )
            failure.denied = True
            raise failure

        getattr(methods, method).side_effect = denied
    context.container.register_instance(NativeKnowledgeEvidence, methods)
    requests = []

    async def streamed(messages, info):
        requests.append(str(messages))
        if len(requests) == 1:
            arguments = (
                {"question": "Read selected evidence"}
                if tool == "search_knowledge"
                else {"dataset_id": asset.id}
            )
            if tool == "propose_catalog_update":
                arguments = {"asset_id": asset.id, "name": "Reviewed rename"}
            if tool == "query_dataset":
                arguments["question"] = "Read selected evidence"
            yield {0: DeltaToolCall(name=tool, json_args=json.dumps(arguments))}
        else:
            yield "UNVERIFIED_TEXT_MUST_NOT_BE_PUBLISHED"

    model = FunctionModel(stream_function=streamed)
    monkeypatch.setattr(ModelFactory, "build_with_secret", lambda self, spec, secret: model)
    thread = await service.create_thread("issuer|admin", "north", {})
    await service.submit(
        "issuer|admin",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Read selected evidence",
            "scope": {"asset_ids": [asset.id]},
            "client_request_id": case,
        },
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("required-provenance")
    await context.get_bean(AssistantExecutor).execute(run.id, "required-provenance")
    if case == "native_denied":
        stored_run = await service.runs.find_by_id(run.id)
        assert stored_run.status == "failed"
        assert stored_run.error_code == "EVIDENCE_UNAVAILABLE"
        assert any(row.kind == "observation" for row in await service.results.find_all(run_id=run.id))
        member = await service.catalog.membership_repository.find_by_id("admin")
        member.active = True
        await service.catalog.membership_repository.save(member)
    answer = (await service.messages("issuer|admin", "north", thread["id"]))[-1]
    assert "UNVERIFIED_TEXT" not in answer["text"]
    assert answer["answer_policy"]["outcome"] == ("review_required" if case == "proposal" else "refused")
    code = {
        "incomplete": "EVIDENCE_PROVENANCE_REQUIRED",
        "schema": "FACTUAL_EVIDENCE_REQUIRED",
        "empty_query": "NO_MATCHING_EVIDENCE",
        "empty_search": "NO_MATCHING_EVIDENCE",
        "proposal": "REVIEW_REQUIRED",
        "native_unavailable": "EVIDENCE_PROVENANCE_REQUIRED",
        "native_denied": "EVIDENCE_UNAVAILABLE",
    }[case]
    assert answer["answer_policy"]["code"] == code
    assert answer["answer_policy"]["reason"]
    if case == "incomplete":
        assert all("BLOCKED_CONTENT_4892" not in value for value in requests)
        assert all(row.kind == "generation" for row in await service.results.find_all(run_id=run.id))
