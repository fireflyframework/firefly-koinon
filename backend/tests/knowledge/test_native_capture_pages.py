# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace

import pytest
from flycanon.core.services.query.provenance import current, observe
from flycanon.core.services.query.search_service import _hit_dto

from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


async def test_native_page_string_and_actual_dto_integer_share_one_immutable_read_identity():
    receipt = NativeEvidenceReceipt("owner", "tenant")
    hit = SimpleNamespace(
        chunk_id="chunk",
        source_id="source",
        content="Exact page content 😀",
        score=1,
        metadata={"page": "3", "section_path": "Scope"},
        knowledge_item_id=None,
        knowledge_version=None,
        bm25_rank=None,
        vector_rank=None,
    )
    with observe(receipt, tenant_id="tenant", workspace_id="workspace", actor="owner"):
        receipt.document_model("retrieval", hit.content, [hit], current())
    before = receipt.documents["chunk"]
    receipt.search("tenant", "workspace", "owner", [_hit_dto(hit).model_dump(mode="json")])
    after = receipt.documents["chunk"]
    assert receipt.complete and before == after and after.page == 3
    assert after.chunk_id == "chunk" and after.source_id == "source"
    assert after.digest == sha256(hit.content.encode()).hexdigest()


@pytest.mark.parametrize(
    "page,expected",
    [
        (3, 3),
        ("3", 3),
        (" +3 ", 3),
        ("0000000003", 3),
        (2147483647, 2147483647),
        ("2147483647", 2147483647),
        (None, None),
        ("", None),
        ("invalid", None),
        (0, None),
        (-1, None),
        (True, None),
        (3.5, None),
        ("٣", None),
        ("2147483648", None),
        (2147483648, None),
        ("9" * 100000, None),
        (b"3", None),
    ],
)
async def test_page_metadata_is_bounded_without_changing_source_or_content_hash(page, expected):
    receipt = NativeEvidenceReceipt("owner", "tenant")
    receipt.search(
        "tenant",
        "workspace",
        "owner",
        [{"chunk_id": "chunk", "source_id": "source", "content": "Exact", "page": page}],
    )
    value = receipt.documents["chunk"]
    assert value.page == expected and value.chunk_id == "chunk" and value.source_id == "source"
    assert value.digest == sha256(b"Exact").hexdigest()
