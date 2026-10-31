# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from flycanon.config import CanonSettings
from flyquery.config import FlyquerySettings
from pyfly.cqrs import DefaultQueryBus
from pyfly.kernel import ForbiddenException
from test_policy_runtime_scope import snapshot

from koinon.knowledge.adapters import NativeDomains
from koinon.knowledge.model_bindings import DomainConnections, KnowledgeConnectionResolver
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot, snapshot_digest
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


def selected(**changes):
    value = snapshot(revision=1).model_dump(mode="json", exclude={"digest"})
    value["documents"].update(changes)
    return OrganizationKnowledgeSnapshot.model_validate({**value, "digest": snapshot_digest(value)})


def domains():
    requests, scopes = [], []

    async def query(request):
        requests.append(request)
        return (
            {"hits": []}
            if hasattr(request.request, "query")
            else {
                "answer": "No matching evidence",
                "citations": [],
                "no_answer": True,
            }
        )

    @asynccontextmanager
    async def resolve(**scope):
        scopes.append(scope)
        yield DomainConnections({}, {})

    beans = {
        CanonSettings: CanonSettings(answer_mode="rag", query_expansion_enabled=False),
        FlyquerySettings: FlyquerySettings(max_refine_retries=2),
        DefaultQueryBus: SimpleNamespace(query=query),
        KnowledgeConnectionResolver: SimpleNamespace(resolve=resolve),
    }
    container = SimpleNamespace(
        contains_type=lambda kind: kind in beans,
        resolve=lambda kind: beans[kind],
        registered_types=lambda: [],
    )
    return NativeDomains(container, admission=WorkAdmission(WorkAdmissionSettings())), requests, scopes, beans


def test_document_role_requirements_follow_the_same_effective_engine_policy():
    adapter, _, _, beans = domains()
    rlm = selected(answer_mode="rlm")
    assert adapter.model_requirements(
        "canon", "search", {"answer": True, "_knowledge_settings_snapshot": rlm}
    ) == ("rlm", ("documents.rlm",))
    assert adapter.model_requirements(
        "canon", "search", {"answer": False, "_knowledge_settings_snapshot": rlm}
    ) == ("search", ("documents.embedding",))
    assert beans[CanonSettings].answer_mode == "rag"


def test_structured_repair_policy_changes_required_roles_without_mutating_deployment():
    adapter, _, _, beans = domains()
    value = selected().model_dump(mode="json", exclude={"digest"})
    value["structured"]["max_refine_retries"] = 0
    policy = OrganizationKnowledgeSnapshot.model_validate({**value, "digest": snapshot_digest(value)})
    purpose, roles = adapter.model_requirements(
        "structured", "query", {"_knowledge_settings_snapshot": policy}
    )
    assert purpose == "query" and "structured.critic" not in roles
    assert beans[FlyquerySettings].max_refine_retries == 2


async def test_rlm_invokes_answer_handler_without_preliminary_hybrid_retrieval():
    from flycanon.core.services.query.handlers import AnswerKnowledgeQuery

    adapter, requests, scopes, beans = domains()
    policy = selected(answer_mode="rlm", rlm_max_iters=3, rlm_extended_reasoning=True)
    await adapter.search(
        tenant_id="north",
        workspace_id="workspace",
        actor="issuer|one",
        source_ids=["admitted-source"],
        question="What is recorded?",
        limit=10,
        answer=True,
        _knowledge_settings_snapshot=policy,
    )
    assert len(requests) == 1 and isinstance(requests[0], AnswerKnowledgeQuery)
    assert requests[0].request.extended_reasoning is True
    assert requests[0].runtime_options.rlm_max_iters == 3
    assert scopes[0]["roles"] == ("documents.rlm",)
    assert beans[CanonSettings].rlm_max_iters == 8


async def test_rag_applies_retrieval_and_answer_limits_to_separate_native_requests():
    from flycanon.core.services.query.handlers import AnswerKnowledgeQuery, SearchKnowledgeQuery

    adapter, requests, _, _ = domains()
    policy = selected(retrieval_top_k=25, retrieval_per_query_k=50, answer_top_k=4)
    await adapter.search(
        tenant_id="north",
        workspace_id="workspace",
        actor="issuer|one",
        source_ids=["admitted-source"],
        question="What is recorded?",
        limit=80,
        answer=True,
        _knowledge_settings_snapshot=policy,
    )
    assert isinstance(requests[0], SearchKnowledgeQuery) and requests[0].request.top_k == 80
    assert requests[0].request.per_query_k == 50
    assert isinstance(requests[1], AnswerKnowledgeQuery) and requests[1].request.top_k == 4
    assert requests[0].runtime_options == requests[1].runtime_options


@pytest.mark.parametrize("sql", [None, "SELECT 1"])
async def test_foreign_policy_is_rejected_before_any_dataset_access(sql):
    adapter, requests, scopes, _ = domains()
    value = selected().model_dump(mode="json", exclude={"digest"})
    value["tenant_id"] = "south"
    policy = OrganizationKnowledgeSnapshot.model_validate({**value, "digest": snapshot_digest(value)})
    with pytest.raises(ForbiddenException, match="another organization"):
        await adapter.query(
            tenant_id="north",
            workspace_id="workspace",
            dataset_id="dataset",
            dataset_allowlist=["dataset"],
            question="facts",
            conversation_id=None,
            sql=sql,
            actor="issuer|one",
            _knowledge_settings_snapshot=policy,
        )
    assert requests == [] and scopes == []


async def test_rlm_shared_receipt_returns_only_parts_admitted_for_the_current_workspace_group():
    from koinon.knowledge.capture_dtos import DocumentRead
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt

    adapter, _, _, beans = domains()
    beans[DefaultQueryBus] = SimpleNamespace(
        query=AsyncMock(return_value={"answer": "Recorded facts", "citations": [], "no_answer": False})
    )
    receipt = NativeEvidenceReceipt("issuer|one", "north")
    for workspace, source, part in (
        ("earlier-workspace", "earlier-source", "earlier-part"),
        ("workspace", "unselected-source", "unselected-part"),
        ("workspace", "selected-source", "selected-part"),
    ):
        receipt.documents[part] = DocumentRead(
            workspace,
            source,
            part,
            "a" * 64,
            "Exact recorded text",
            None,
            None,
            source_version_id="version",
            extraction_id="extraction",
            source_part_id=part,
            source_part_sha256="b" * 64,
            recorded_page=7,
        )
    result = await adapter.search(
        tenant_id="north",
        workspace_id="workspace",
        source_ids=["selected-source"],
        question="Recorded facts?",
        limit=10,
        answer=True,
        actor="issuer|one",
        _knowledge_settings_snapshot=selected(answer_mode="rlm"),
        _capture=receipt,
    )
    assert [hit["chunk_id"] for hit in result["hits"]] == ["selected-part"]
    assert result["hits"][0]["metadata"]["recorded_page"] == 7
    assert set(receipt.documents) == {"earlier-part", "unselected-part", "selected-part"}
