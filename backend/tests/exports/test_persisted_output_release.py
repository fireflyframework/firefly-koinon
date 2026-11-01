# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import copy
import importlib.util
from pathlib import Path

import pytest
from pyfly.kernel import ServiceUnavailableException

from koinon.evidence.repositories import EvidenceReviewRepository
from koinon.exports.dtos import ConversationExportInput, ExportCreate
from koinon.exports.service import KnowledgeExports
from koinon.sharing.dtos import ShareCreate, ShareReviewInput
from koinon.sharing.service import ConversationShares

spec = importlib.util.spec_from_file_location(
    "persisted_output_fixture", Path(__file__).resolve().parents[1] / "evidence/test_evidence_reviews.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
reviews = module.reviews


@pytest.mark.parametrize("kind", ["export", "share"])
async def test_persisted_legacy_assistant_text_cannot_transfer_without_output_authority(reviews, kind):
    evidence, _, context = reviews
    evidence.outputs = None
    if kind == "export":
        service = context.get_bean(KnowledgeExports)
        preview = await service.preview(
            "owner",
            "north",
            ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="json"),
        )
        created = await service.create(
            "owner", "north", ExportCreate(review_id=preview.id, expected_revision=preview.revision)
        )
        transfer = service.download
    else:
        service = context.get_bean(ConversationShares)
        preview = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
        created = await service.create(
            "owner", "north", ShareCreate(review_id=preview.id, expected_revision=preview.revision)
        )
        transfer = service.read
    repository = context.get_bean(EvidenceReviewRepository)
    before = copy.deepcopy((await repository.find_by_id(preview.id)).snapshot_json)
    with pytest.raises(ServiceUnavailableException) as error:
        await transfer("owner", "north", created.id)
    assert error.value.code == "CONVERSATION_OUTPUT_UNAVAILABLE"
    assert (await repository.find_by_id(preview.id)).snapshot_json == before


async def test_user_only_stored_export_does_not_require_optional_assistant_module(reviews):
    evidence, _, context = reviews
    evidence.outputs = None
    service = context.get_bean(KnowledgeExports)
    preview = await service.preview(
        "owner",
        "north",
        ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="json"),
    )
    created = await service.create(
        "owner", "north", ExportCreate(review_id=preview.id, expected_revision=preview.revision)
    )
    repository = context.get_bean(EvidenceReviewRepository)
    row = await repository.find_by_id(preview.id)
    payload = copy.deepcopy(row.snapshot_json)
    payload["messages"][0]["role"] = "user"
    row.snapshot_json = payload
    await repository.save(row)
    assert b"Reviewed answer" in (await service.download("owner", "north", created.id)).content


@pytest.mark.parametrize("kind", ["export", "share"])
async def test_output_authority_rechecked_after_render_or_source_resolution(reviews, kind):
    from types import SimpleNamespace

    from koinon.catalog.errors import AccessDenied

    evidence, _, context = reviews
    if kind == "export":
        service = context.get_bean(KnowledgeExports)
        preview = await service.preview(
            "owner",
            "north",
            ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="json"),
        )
        created = await service.create(
            "owner", "north", ExportCreate(review_id=preview.id, expected_revision=preview.revision)
        )
        transfer = service.download
    else:
        service = context.get_bean(ConversationShares)
        preview = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
        created = await service.create(
            "owner", "north", ShareCreate(review_id=preview.id, expected_revision=preview.revision)
        )
        transfer = service.read
    calls = []

    class Outputs:
        async def authorize_output(self, subject, tenant_id, thread_id, message_ids, *, snapshot=None):
            calls.append((subject, tenant_id, thread_id, message_ids))
            assert snapshot.messages[0].text == "Reviewed answer"
            if len(calls) == 2:
                raise AccessDenied("Regenerate this answer", code="ANSWER_RELEASE_UNAVAILABLE")

    evidence.outputs = SimpleNamespace(get=lambda: Outputs())
    with pytest.raises(AccessDenied) as error:
        await transfer("owner", "north", created.id)
    assert error.value.code == "ANSWER_RELEASE_UNAVAILABLE"
    assert calls == [("owner", "north", "t", ["m"])] * 2
