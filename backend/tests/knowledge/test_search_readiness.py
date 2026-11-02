# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.kernel import ConflictException
from test_facade import context as context
from test_facade import upload

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence


async def unfinished(context, status="pending"):
    _, catalog, _, tree, _ = context
    source = await catalog.create(
        "issuer|admin", "north", kind="source", name="Retained original", parent_id=tree["collection"].id
    )
    document = await catalog.create(
        "issuer|admin", "north", kind="document", name="Unfinished document", parent_id=source.id
    )
    return await catalog.update("issuer|admin", "north", document.id, {"status": status})


@pytest.mark.parametrize("status", ["pending", "error", "failed"])
async def test_broad_search_authorizes_then_skips_unfinished_unbound_documents(context, status):
    facade, _, domains, _, _ = context
    await unfinished(context, status)
    ready = (await upload(context))["assets"][0]
    result = await facade.search("issuer|reader", "north", question="evidence")
    assert result["hits"] == []
    assert domains.search.await_args.kwargs["source_ids"] == ["native-source"]
    capture = domains.search.await_args.kwargs["_capture"]
    assert set(capture.canonical_documents.values()) == {ready["id"]}


async def test_explicit_unfinished_document_returns_actionable_not_ready(context):
    facade, _, domains, _, _ = context
    document = await unfinished(context)
    with pytest.raises(ConflictException) as error:
        await facade.search("issuer|reader", "north", question="evidence", asset_ids=[document.id])
    assert error.value.code == "DOCUMENT_NOT_READY"
    domains.search.assert_not_awaited()


async def test_ready_document_with_missing_binding_still_fails_closed(context):
    facade, _, domains, _, _ = context
    await unfinished(context, "ready")
    with pytest.raises(AccessDenied) as error:
        await facade.search("issuer|reader", "north", question="evidence")
    assert error.value.code == "BINDING_UNAVAILABLE"
    domains.search.assert_not_awaited()


async def test_pending_status_never_swallows_current_authority_denial(context, monkeypatch):
    facade, _, domains, _, _ = context
    document = await unfinished(context)
    original = facade._chain
    observed = []

    async def revoked(subject, tenant, identifier, permission="catalog:read"):
        if identifier == document.id:
            observed.append(identifier)
            raise AccessDenied("Current source permission was revoked", code="ACCESS_DENIED")
        return await original(subject, tenant, identifier, permission)

    monkeypatch.setattr(facade, "_chain", revoked)
    with pytest.raises(AccessDenied):
        await facade.search("issuer|reader", "north", question="evidence")
    assert observed == [document.id]
    domains.search.assert_not_awaited()


@pytest.mark.parametrize("pending", [False, True])
@pytest.mark.parametrize("answer", [False, True])
async def test_empty_eligible_catalog_has_complete_empty_evidence_without_claiming_native_read(
    context, pending, answer
):
    facade, _, domains, tree, native = context
    if pending:
        await unfinished(context)
    evidence = NativeKnowledgeEvidence(facade, native.get_bean(DataSourceRegistry))
    capture = await evidence.search(
        "issuer|reader", "north", question="evidence", workspace_id=tree["workspace"].id, answer=answer
    )
    assert capture.complete is True
    assert capture.data["hits"] == []
    assert capture.sources == capture.native_reads == capture.sql_attempts == ()
    if answer:
        assert capture.data["answer"] == "" and capture.data["citations"] == []
    domains.search.assert_not_awaited()


async def test_unobserved_empty_payload_alone_cannot_claim_complete_catalog_search():
    knowledge = SimpleNamespace(search=AsyncMock(return_value={"hits": []}))
    capture = await NativeKnowledgeEvidence(knowledge, None).search(
        "issuer|reader", "north", question="evidence"
    )
    assert capture.complete is False
    assert capture.sources == capture.native_reads == ()


@pytest.mark.parametrize(
    "data",
    [
        {"hits": [{"text": "Unobserved"}]},
        {"hits": [], "answer": "Unobserved"},
        {"hits": [], "citations": [{"id": "unobserved"}]},
    ],
)
async def test_catalog_empty_marker_never_attests_source_or_model_content(data):
    async def search(subject, tenant, **arguments):
        arguments["_capture"].empty_catalog_search(subject, tenant, AsyncMock())
        return data

    knowledge = SimpleNamespace(search=search)
    capture = await NativeKnowledgeEvidence(knowledge, None).search(
        "issuer|reader", "north", question="evidence"
    )
    assert capture.complete is False
    assert capture.sources == capture.native_reads == ()


async def test_empty_catalog_authority_is_rechecked_before_receipt_release(context, monkeypatch):
    facade, _, domains, tree, native = context
    original = facade._chain
    calls = []

    async def current(*args, **kwargs):
        calls.append(args[2])
        if len(calls) == 3:
            raise AccessDenied("Authority was revoked", code="ACCESS_DENIED")
        return await original(*args, **kwargs)

    monkeypatch.setattr(facade, "_chain", current)
    with pytest.raises(AccessDenied):
        await NativeKnowledgeEvidence(facade, native.get_bean(DataSourceRegistry)).search(
            "issuer|reader", "north", question="evidence", workspace_id=tree["workspace"].id
        )
    assert len(calls) == 3
    domains.search.assert_not_awaited()
