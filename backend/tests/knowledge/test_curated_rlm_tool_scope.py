# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Document and curated scopes remain typed and distinct in old and new audits."""

import pytest
from pydantic import ValidationError
from test_rlm_tool_receipts import tool

from koinon.assistants.audit_dtos import RlmToolReceipt
from koinon.knowledge.capture_dtos import NativeRlmTool


def _wire(**changes):
    return {
        "result_id": "result",
        "tenant_id": "north",
        "workspace_id": "native",
        **tool().model_dump(mode="json"),
        "source_ids": ["source"],
        **changes,
    }


def test_old_document_receipts_retain_exact_unset_serialization_and_empty_knowledge_default():
    wire = _wire()
    parsed = RlmToolReceipt.model_validate(wire)
    assert parsed.model_dump(mode="json", exclude_unset=True) == wire
    assert parsed.knowledge_item_ids == []
    native = {key: value for key, value in wire.items() if key != "result_id"}
    native["source_ids"] = tuple(native["source_ids"])
    parsed_native = NativeRlmTool.model_validate(native)
    assert parsed_native.knowledge_item_ids == ()
    assert parsed_native.model_dump(mode="json", exclude_unset=True) == {
        key: value for key, value in wire.items() if key != "result_id"
    }


@pytest.mark.parametrize(
    ("documents", "knowledge"), [([], ["item"]), (["source"], ["item"]), (["same"], ["same"])]
)
def test_knowledge_only_and_mixed_receipts_never_relabel_knowledge_as_documents(documents, knowledge):
    wire = _wire(source_ids=documents, knowledge_item_ids=knowledge)
    parsed = RlmToolReceipt.model_validate(wire)
    assert parsed.source_ids == documents and parsed.knowledge_item_ids == knowledge
    native = {key: value for key, value in wire.items() if key != "result_id"}
    native.update(source_ids=tuple(documents), knowledge_item_ids=tuple(knowledge))
    parsed_native = NativeRlmTool.model_validate(native)
    assert parsed_native.source_ids == tuple(documents)
    assert parsed_native.knowledge_item_ids == tuple(knowledge)


@pytest.mark.parametrize(
    ("documents", "knowledge"),
    [
        ([], []),
        (["a", "a"], []),
        ([], ["a", "a"]),
        (["x" * 65], []),
        ([], [3]),
        ([False], []),
        ([], [""]),
        (["x"] * 501, []),
        ([str(i) for i in range(300)], [str(i) for i in range(201)]),
    ],
)
def test_scope_requires_unique_bounded_identifiers_and_at_least_one_resource(documents, knowledge):
    with pytest.raises(ValidationError):
        RlmToolReceipt.model_validate(_wire(source_ids=documents, knowledge_item_ids=knowledge))
