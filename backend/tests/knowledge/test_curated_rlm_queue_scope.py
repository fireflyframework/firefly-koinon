# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persisted tool scope cannot borrow an identifier from another provenance domain."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import InvalidRequestException
from test_rlm_tool_receipts import tool

from koinon.assistants.queue import AssistantQueue
from koinon.knowledge.capture_dtos import CapturedEvidence, NativeReadFingerprint, NativeRlmTool


def queue():
    return AssistantQueue(
        SimpleNamespace(
            threads=SimpleNamespace(find_by_id=AsyncMock(return_value=SimpleNamespace(subject="reader"))),
            catalog=SimpleNamespace(
                get=AsyncMock(return_value=SimpleNamespace(tenant_id="north", workspace_id="canonical"))
            ),
        )
    )


def capture(*, document_ids=(), knowledge_ids=("item",), domain="knowledge"):
    read = NativeReadFingerprint(
        "rlm.root",
        domain,
        "north",
        "canonical",
        "item",
        "a" * 64,
        ("item",),
        (),
        read_kind="knowledge_version" if domain == "knowledge" else "metadata",
        knowledge_item_id="item" if domain == "knowledge" else None,
        knowledge_version_id="version" if domain == "knowledge" else None,
        knowledge_version=1 if domain == "knowledge" else None,
    )
    action = NativeRlmTool(
        **tool().model_dump(),
        tenant_id="north",
        workspace_id="native",
        source_ids=document_ids,
        knowledge_item_ids=knowledge_ids,
    )
    return CapturedEvidence({}, (), False, (read,), (), (action,))


async def test_knowledge_scope_survives_typed_queue_serialization_without_fabricated_document_ids():
    values = await queue().native_receipts(
        SimpleNamespace(tenant_id="north", thread_id="thread"), ["item"], capture(), "result", "generation"
    )
    assert values["rlm_tools"][0]["source_ids"] == []
    assert values["rlm_tools"][0]["knowledge_item_ids"] == ["item"]


@pytest.mark.parametrize(
    "options",
    [
        {"knowledge_ids": ("forged",)},
        {"knowledge_ids": (), "document_ids": ("item",)},
        {"domain": "documents", "knowledge_ids": ("item",)},
    ],
)
async def test_tool_identity_requires_its_own_observed_domain(options):
    with pytest.raises(InvalidRequestException) as caught:
        await queue().native_receipts(
            SimpleNamespace(tenant_id="north", thread_id="thread"),
            ["item"],
            capture(**options),
            "result",
            "generation",
        )
    assert caught.value.code == "EVIDENCE_CAPTURE_INVALID"
