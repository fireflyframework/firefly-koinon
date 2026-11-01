# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from pyfly.kernel import ConflictException

from koinon.knowledge.curated.dtos import KnowledgeIntentInput
from koinon.knowledge.curated.repositories import KnowledgeIntentRepository

spec = importlib.util.spec_from_file_location(
    "persisted_curated_fixture", Path(__file__).with_name("test_curated_intents.py")
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
curated = module.curated


@pytest.mark.parametrize("capture", [None, {"messages": []}])
async def test_old_conversation_intent_requires_current_answer_output_authority(curated, capture):
    service, _, destination, context = curated
    preview = await service.preview(
        "issuer|owner", "north", KnowledgeIntentInput.model_validate(module.input_for(destination))
    )
    repository = context.get_bean(KnowledgeIntentRepository)
    row = await repository.find_by_id(preview.id)
    row.request_json = {
        **row.request_json,
        "origin": {"kind": "conversation", "thread_id": "thread", "message_ids": ["legacy-answer"]},
    }
    if capture is not None:
        row.request_json = {**row.request_json, "_output_context": capture}
    await repository.save(row)
    from types import SimpleNamespace

    class CurrentSealedAnswer:
        async def authorize_output(self, *args, **kwargs):
            return None

    service.authority.outputs = SimpleNamespace(get=lambda: CurrentSealedAnswer())
    with pytest.raises(ConflictException) as error:
        await service.get("issuer|owner", "north", preview.id)
    assert error.value.code == "KNOWLEDGE_OUTPUT_REVIEW_REQUIRED"
    unchanged = await repository.find_by_id(preview.id)
    assert unchanged.status == "preview" and unchanged.request_json == row.request_json


@pytest.mark.parametrize("oversized", [False, True])
async def test_new_preview_binds_exact_selected_text_privately_and_does_not_follow_regeneration(
    curated, oversized
):
    from types import SimpleNamespace

    from koinon.catalog.errors import AccessDenied
    from koinon.evidence.dtos import ConversationMessage, ConversationSnapshot, SourceReference
    from koinon.knowledge.curated.authority import digest

    service, catalog, destination, context = curated
    source = await catalog.create(
        "issuer|owner", "north", kind="source", name="Source", parent_id=destination.id
    )
    document = await catalog.create(
        "issuer|owner", "north", kind="document", name="Document", parent_id=source.id
    )
    reference = SourceReference(
        id="part",
        asset_id=document.id,
        source_id=source.id,
        title="Document",
        kind="document",
        used_revision="chunk-sha256:" + "a" * 64,
        chunk_id="chunk",
        quote="Exact source fact",
    )
    snapshot = ConversationSnapshot(
        thread_id="thread",
        tenant_id="north",
        owner_subject="issuer|owner",
        title="Selected answer",
        revision="b" * 64,
        source_manifest_complete=True,
        sources=(reference,),
        messages=(
            ConversationMessage(
                id="answer", role="assistant", text="Exact source fact", status="completed", revision="c" * 64
            ),
        ),
    )
    if oversized:
        snapshot = snapshot.model_copy(
            update={
                "messages": tuple(
                    snapshot.messages[0].model_copy(
                        update={"id": "answer-" + str(index), "text": "x" * 1_000_000}
                    )
                    for index in range(6)
                )
            }
        )
    current_text = snapshot.messages[0].text
    observed = []

    class Snapshots:
        async def snapshot(self, *args):
            return snapshot

    class Sources:
        async def resolve(self, subject, tenant_id, sources):
            return tuple(
                value.model_copy(
                    update={"availability": "available", "current_revision": value.used_revision}
                )
                for value in sources
            )

    class Outputs:
        async def authorize_output(self, subject, tenant_id, thread_id, message_ids, *, snapshot=None):
            observed.append(snapshot)
            if snapshot.messages[0].text != current_text:
                raise AccessDenied("Selected output changed", code="EVIDENCE_RELEASE_REQUIRED")

    service.authority.snapshots = SimpleNamespace(get=lambda: Snapshots())
    service.authority.sources = SimpleNamespace(get=lambda: Sources())
    service.authority.outputs = SimpleNamespace(get=lambda: Outputs())
    request = module.input_for(
        destination,
        origin={
            "kind": "conversation",
            "thread_id": "thread",
            "message_ids": [message.id for message in snapshot.messages],
        },
    )
    if oversized:
        from pyfly.kernel import PayloadTooLargeException

        with pytest.raises(PayloadTooLargeException) as error:
            await service.preview("issuer|owner", "north", request)
        assert error.value.code == "SNAPSHOT_TOO_LARGE"
        assert not await context.get_bean(KnowledgeIntentRepository).find_all(tenant_id="north")
        return
    preview = await service.preview("issuer|owner", "north", request)
    row = await context.get_bean(KnowledgeIntentRepository).find_by_id(preview.id)
    assert row.request_json["_output_context"]["messages"][0]["text"] == "Exact source fact"
    assert "_output_context" not in preview.model_dump()
    assert row.authorization_digest == digest(
        {
            "id": row.id,
            "revision": row.revision,
            "subject": row.subject,
            "tenant_id": row.tenant_id,
            "request": row.request_json,
            "destination": row.destination_json,
            "evidence": row.evidence_json,
            "before": row.before_json,
            "target": row.target_item_id,
            "origins": row.originating_token_ids,
            "expires_at": row.expires_at.isoformat(),
        }
    )
    await service.get("issuer|owner", "north", preview.id)
    assert observed[-1].messages[0].text == "Exact source fact"
    current_text = "A later independently sealed answer"
    with pytest.raises(AccessDenied) as error:
        await service.get("issuer|owner", "north", preview.id)
    assert error.value.code == "EVIDENCE_RELEASE_REQUIRED"
    assert (
        await context.get_bean(KnowledgeIntentRepository).find_by_id(preview.id)
    ).request_json == row.request_json
