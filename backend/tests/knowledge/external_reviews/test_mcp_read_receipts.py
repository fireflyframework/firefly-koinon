# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.capture_dtos import CapturedEvidence


def security(identifier="origin"):
    return SecurityContextHolder.using(
        SecurityContext(
            user_id="owner", attributes={"iss": "issuer", "sub": "owner", "koinon_token_id": identifier}
        )
    )


async def setup_receipt(reviewed):
    from koinon.knowledge.external_reviews.read_receipts import ExternalReadReceipts
    from koinon.tokens.repositories import PersonalTokenRepository

    service, _, destination, context = reviewed
    tokens = context.get_bean(PersonalTokenRepository)
    for identifier in ("origin", "other"):
        token = await tokens.find_by_id(identifier)
        token.scopes = [*token.scopes, "knowledge:search"]
        await tokens.save(token)
    source = SourceReference(
        id="read-source",
        asset_id=destination.id,
        kind="document",
        title="Actual selected chunk",
        source_id="parent",
        chunk_id="chunk",
        used_revision="chunk-sha256:" + "a" * 64,
        quote="Actual source bytes",
    )
    receipts = context.get_bean(ExternalReadReceipts)

    async def resolve(subject, tenant_id, sources):
        return tuple(
            value.model_copy(update={"availability": "available", "current_revision": value.used_revision})
            for value in sources
        )

    receipts.sources = SimpleNamespace(get=lambda: SimpleNamespace(resolve=resolve))
    return receipts, source, context, tokens


async def test_real_capture_receipt_is_immutable_and_reauthenticates_exact_credential(reviewed):
    receipts, source, context, _ = await setup_receipt(reviewed)
    with security():
        issued = await receipts.record(
            "issuer|owner",
            "north",
            "search",
            {"question": "actual"},
            CapturedEvidence({"hits": [{"text": "Actual source bytes"}]}, (source,), True),
        )
        resolved, origins = await receipts.resolve("issuer|owner", "north", (issued["id"],))
    assert resolved == (source,) and origins == ("origin",)
    assert issued["status"] == "recorded" and issued["sources"][0]["quote"] == source.quote
    assert issued["expires_at"] <= (datetime.now(UTC) + timedelta(seconds=301)).isoformat()
    for identifier, subject, tenant in [
        ("other", "issuer|owner", "north"),
        ("origin", "issuer|foreign", "north"),
        ("origin", "issuer|owner", "south"),
    ]:
        with security(identifier), pytest.raises(AccessDenied):
            await receipts.resolve(subject, tenant, (issued["id"],))
    with security(), pytest.raises(AccessDenied):
        await receipts.resolve("issuer|owner", "north", ("forged",))


@pytest.mark.parametrize(
    "mutation",
    ["expired", "tampered", "revoked", "changed_scope", "stale", "membership_removed", "workspace_changed"],
)
async def test_expired_tampered_revoked_changed_scope_and_stale_sources_fail_closed(reviewed, mutation):
    from koinon.knowledge.external_reviews.read_receipt_repositories import ExternalReadReceiptRepository

    receipts, source, context, tokens = await setup_receipt(reviewed)
    with security():
        issued = await receipts.record(
            "issuer|owner", "north", "search", {}, CapturedEvidence({}, (source,), True)
        )
    repository = context.get_bean(ExternalReadReceiptRepository)
    row = await repository.find_by_id(issued["id"])
    if mutation == "expired":
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await repository.save(row)
    elif mutation == "tampered":
        row.sources_json = [source.model_copy(update={"quote": "Altered bytes"}).model_dump(mode="json")]
        await repository.save(row)
    elif mutation in {"revoked", "changed_scope"}:
        token = await tokens.find_by_id("origin")
        if mutation == "revoked":
            token.revoked_at = datetime.now(UTC)
        else:
            token.scopes = ["catalog:read"]
        await tokens.save(token)
    elif mutation == "membership_removed":
        from koinon.catalog.repositories import MembershipRepository

        await context.get_bean(MembershipRepository).delete_by_id("owner")
    elif mutation == "workspace_changed":
        token = await tokens.find_by_id("origin")
        token.workspace_ids = ["foreign-workspace"]
        await tokens.save(token)
    else:

        async def stale(*args):
            return (source.model_copy(update={"availability": "changed", "current_revision": "new"}),)

        receipts.sources = SimpleNamespace(get=lambda: SimpleNamespace(resolve=stale))
    with security(), pytest.raises(AccessDenied):
        await receipts.resolve("issuer|owner", "north", (issued["id"],))


async def test_incomplete_unsupported_empty_and_bounded_receipts_are_not_recorded(reviewed):
    receipts, source, _, _ = await setup_receipt(reviewed)
    with security():
        for captured in [
            CapturedEvidence({}, (), True),
            CapturedEvidence({}, (source,), False),
            CapturedEvidence({}, (source,) * 65, True),
        ]:
            result = await receipts.record("issuer|owner", "north", "search", {}, captured)
            assert result["status"] == "not_recorded" and result.get("id") is None
        receipts.settings.max_active_receipts = 1
        first = await receipts.record(
            "issuer|owner", "north", "search", {}, CapturedEvidence({}, (source,), True)
        )
        limited = await receipts.record(
            "issuer|owner", "north", "search", {}, CapturedEvidence({}, (source,), True)
        )
    assert first["id"] and limited["reason"] == "active_receipt_limit"
    with security(), pytest.raises(AccessDenied):
        await receipts.resolve("issuer|owner", "north", (first["id"], first["id"]))


async def test_expired_receipts_do_not_exhaust_active_quota_and_history_remains(reviewed):
    receipts, source, _, _ = await setup_receipt(reviewed)
    receipts.settings.max_active_receipts = 1
    with security():
        first = await receipts.record(
            "issuer|owner", "north", "search", {}, CapturedEvidence({}, (source,), True)
        )
        row = await receipts.receipts.find_by_id(first["id"])
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await receipts.receipts.save(row)
        second = await receipts.record(
            "issuer|owner", "north", "search", {}, CapturedEvidence({}, (source,), True)
        )
    assert second["status"] == "recorded"
    assert await receipts.receipts.find_by_id(first["id"]) is not None


async def test_capture_bytes_are_bounded_before_persistence(reviewed):
    receipts, source, _, _ = await setup_receipt(reviewed)
    receipts.settings.max_receipt_bytes = 1024
    source = source.model_copy(update={"quote": "x" * 8000})
    with security():
        result = await receipts.record(
            "issuer|owner", "north", "fetch", {}, CapturedEvidence({}, (source,), True)
        )
    assert result == {"status": "not_recorded", "reason": "receipt_byte_limit", "sources": []}
    assert await receipts.receipts.count() == 0


async def test_native_search_adapter_captures_actual_read_once_without_client_manifest(reviewed, monkeypatch):
    from hashlib import sha256
    from unittest.mock import AsyncMock

    from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence
    from koinon.mcp import read_capture

    receipts, source, _, _ = await setup_receipt(reviewed)
    text = "Exact read bytes 😀"
    document = SimpleNamespace(id=source.asset_id, name=source.title, kind="document", workspace_id="space")
    parent = SimpleNamespace(id="parent")
    binding = SimpleNamespace(native_id="native-source", native_workspace_id="native-space")
    data = {"hits": [{"id": "chunk", "asset_id": document.id, "source_id": "parent", "text": text}]}

    async def search(subject, tenant, **arguments):
        assert subject == "issuer|owner" and tenant == "north"
        arguments["_capture"].search(
            tenant,
            "native-space",
            subject,
            [
                {
                    "chunk_id": "chunk",
                    "source_id": "native-source",
                    "content": text,
                    "page": 3,
                    "section_path": "Actual section",
                }
            ],
        )
        return data

    knowledge = SimpleNamespace(
        _chain=AsyncMock(return_value=[document, parent]),
        binding=AsyncMock(return_value=binding),
        search=AsyncMock(side_effect=search),
    )
    native = NativeKnowledgeEvidence(knowledge, SimpleNamespace())

    async def authenticate(context, raw, work):
        assert raw == "actual-private-token"
        with security():
            return await work("issuer|owner")

    monkeypatch.setattr(read_capture, "authenticated_operation", authenticate)
    context = SimpleNamespace(get_bean=lambda kind: native if kind is NativeKnowledgeEvidence else receipts)
    result = await read_capture.native_read_capture(context)(
        "actual-private-token", "north", "search", {"question": "Actual question", "answer": False}
    )
    assert knowledge.search.await_count == 1 and result["hits"] == data["hits"]
    actual = result["read_receipt"]["sources"][0]
    assert actual["used_revision"] == "chunk-sha256:" + sha256(text.encode()).hexdigest()
    assert actual["quote"] == text and actual["page"] == 3 and actual["source_version_id"] is None
    with security():
        resolved, origins = await receipts.resolve("issuer|owner", "north", (result["read_receipt"]["id"],))
    assert resolved[0].quote == text and origins == ("origin",)


@pytest.mark.parametrize("tool_state", ["unknown", "empty", "recorded"])
async def test_read_receipt_preserves_actual_tool_trace_and_unknown_history(reviewed, tool_state):
    from koinon.knowledge.capture_dtos import NativeRlmTool

    receipts, source, _, _ = await setup_receipt(reviewed)
    tool = NativeRlmTool(
        tenant_id="north",
        workspace_id="space",
        source_ids=("parent",),
        tool_call_id="actual-call",
        tool_name="python",
        request_sha256="1" * 64,
        schema_sha256="2" * 64,
        arguments_sha256="3" * 64,
        result_sha256="4" * 64,
        execution_sha256="5" * 64,
        result_kind="tool_return",
        outcome="completed",
        execution_status="completed",
        execution_state="ready",
    )
    tools = None if tool_state == "unknown" else () if tool_state == "empty" else (tool,)
    with security():
        issued = await receipts.record(
            "issuer|owner", "north", "search", {}, CapturedEvidence({}, (source,), True, rlm_tools=tools)
        )
    row = await receipts.receipts.find_by_id(issued["id"])
    assert row.provenance_json["rlm_tools"] == (
        None if tools is None else [v.model_dump(mode="json") for v in tools]
    )
