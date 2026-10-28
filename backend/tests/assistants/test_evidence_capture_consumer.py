# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace

import pytest
from pyfly.kernel import InvalidRequestException
from test_catalog_proposals import proposal_fixture
from test_service import assistants as assistants

from koinon.assistants.queue import AssistantQueue
from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import SourceReference
from koinon.evidence.ports import ConversationSnapshotPort


async def fixture(assistants):
    service, context = assistants
    _, _, run, entry = await proposal_fixture(service, context)
    data = {
        "hits": [
            {
                "id": "chunk",
                "asset_id": entry.id,
                "source_id": entry.parent_id,
                "title": entry.name,
                "text": "Verified native chunk",
            }
        ]
    }
    source = SourceReference(
        id="receipt",
        asset_id=entry.id,
        source_id=entry.parent_id,
        title=entry.name,
        kind="document",
        chunk_id="chunk",
        quote="Verified native chunk",
        used_revision="chunk-sha256:" + "a" * 64,
    )
    return service, context, run, entry, data, source


async def test_only_separate_typed_receipt_can_make_new_source_manifest_complete(assistants):
    from koinon.knowledge.evidence_capture import CapturedEvidence

    service, context, run, entry, data, source = await fixture(assistants)
    queue = context.get_bean(AssistantQueue)
    result_id = await queue.evidence(
        run.id, "proposal-worker", "search", data, [entry.id], capture=CapturedEvidence(data, (source,), True)
    )
    payload = (await service.results.find_by_id(result_id)).payload
    assert payload["source_manifest"] == {
        "version": 1,
        "complete": True,
        "sources": [source.model_dump(mode="json")],
    }
    await queue.policy(run.id, "proposal-worker", {"outcome": "grounded"})
    await queue.finish(run.id, "proposal-worker")
    message = await service.message_repository.find_by_id(run.message_id)
    message.artifacts = [value for value in message.artifacts if value["id"] == result_id]
    await service.message_repository.save(message)
    snapshot = await context.get_bean(ConversationSnapshotPort).snapshot(
        "issuer|admin", "north", run.thread_id, [run.message_id]
    )
    assert snapshot.source_manifest_complete is True
    assert snapshot.sources[0].used_revision == source.used_revision
    assert snapshot.sources[0].current_revision is None


async def test_nested_model_json_cannot_be_promoted_to_trusted_source_provenance(assistants):
    from pyfly.kernel import ServiceUnavailableException

    service, context, run, entry, data, source = await fixture(assistants)
    data["source_manifest"] = {"version": 1, "complete": True, "sources": [source.model_dump(mode="json")]}
    before = len(await service.results.find_all(run_id=run.id))
    with pytest.raises(ServiceUnavailableException) as error:
        await context.get_bean(AssistantQueue).evidence(run.id, "proposal-worker", "search", data, [entry.id])
    assert error.value.code == "EVIDENCE_PROVENANCE_REQUIRED"
    assert len(await service.results.find_all(run_id=run.id)) == before


@pytest.mark.parametrize("case", ["data", "boolean", "assets", "unknown_revision", "duplicate"])
async def test_receipts_cannot_attest_other_data_or_incomplete_claims(assistants, case):
    from koinon.knowledge.evidence_capture import CapturedEvidence

    service, context, run, entry, data, source = await fixture(assistants)
    receipt = CapturedEvidence(data, (source,), True)
    if case == "data":
        receipt = replace(receipt, data={"hits": []})
    if case == "boolean":
        data = {**data, "counter": True}
        receipt = replace(receipt, data={**data, "counter": 1})
    if case == "assets":
        receipt = replace(receipt, sources=(source.model_copy(update={"asset_id": "other"}),))
    if case == "unknown_revision":
        receipt = replace(receipt, sources=(source.model_copy(update={"used_revision": None}),))
    if case == "duplicate":
        receipt = replace(receipt, sources=(source, source))
    before = len(await service.results.find_all(run_id=run.id))
    with pytest.raises(InvalidRequestException):
        await context.get_bean(AssistantQueue).evidence(
            run.id, "proposal-worker", "search", data, [entry.id], capture=receipt
        )
    assert len(await service.results.find_all(run_id=run.id)) == before


async def test_capture_persistence_rechecks_revoked_source_authority(assistants):
    from koinon.knowledge.evidence_capture import CapturedEvidence

    service, context, run, entry, data, source = await fixture(assistants)
    membership = await service.catalog.membership_repository.find_by_id("admin")
    membership.active = False
    await service.catalog.membership_repository.save(membership)
    with pytest.raises(AccessDenied):
        await context.get_bean(AssistantQueue).evidence(
            run.id,
            "proposal-worker",
            "search",
            data,
            [entry.id],
            capture=CapturedEvidence(data, (source,), True),
        )
