# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from test_curated_intents import committed_projection, input_for
from test_curated_intents import curated as curated


async def test_uncertain_native_commit_reconciles_the_same_receipt_without_a_second_write(curated):
    from koinon.knowledge.curated.authority import digest
    from koinon.knowledge.curated.dtos import KnowledgeCommitReceipt
    from koinon.knowledge.curated.ports import NativeCommitUncertain

    service, _, destination, context = curated
    preview = await service.preview(
        "issuer|owner", "north", input_for(destination, action="create_published")
    )

    class Port:
        commits = 0
        stored = None

        async def projection(self, subject, tenant_id, receipt):
            return await committed_projection(context, preview, receipt)

        async def receipt(self, *args):
            return self.stored

        async def commit(self, operation):
            self.commits += 1
            self.stored = KnowledgeCommitReceipt(
                operation_id=preview.id,
                intent_id=preview.id,
                intent_revision=1,
                authorization_digest=preview.authorization_digest,
                item_id=preview.target_item_id,
                native_item_id=preview.target_item_id,
                native_version_id="native-v1",
                version=1,
                serving_version=1,
                action=preview.action,
                content_sha256=digest(preview.after.model_dump(mode="json")),
                evidence_sha256=digest([value.model_dump(mode="json") for value in preview.evidence]),
                committed_at=datetime.now(UTC),
                retrieval_state="lexical_ready",
            )
            raise NativeCommitUncertain()

    port = Port()
    service.native = SimpleNamespace(get=lambda: port)
    confirmation = {
        "confirm": True,
        "expected_revision": 1,
        "authorization_digest": preview.authorization_digest,
    }
    pending = await service.confirm("issuer|owner", "north", preview.id, confirmation, "explicit-review")
    assert pending.status == "pending" and port.commits == 1
    assert (await service.get("issuer|owner", "north", preview.id)).receipt == port.stored
    result = await service.confirm("issuer|owner", "north", preview.id, confirmation, "explicit-review")
    assert result.status == "committed" and result.receipt == port.stored
    assert port.commits == 1
    assert (await service.get("issuer|owner", "north", preview.id)).status == "committed"


async def test_definitive_native_version_conflict_requires_a_fresh_review(curated):
    from pyfly.kernel import ConflictException

    service, _, destination, _ = curated
    preview = await service.preview("issuer|owner", "north", input_for(destination))

    class Port:
        async def receipt(self, *args):
            return None

        async def commit(self, operation):
            raise ConflictException("Version changed", code="KNOWLEDGE_VERSION_CONFLICT")

    service.native = SimpleNamespace(get=lambda: Port())
    confirmation = {
        "confirm": True,
        "expected_revision": 1,
        "authorization_digest": preview.authorization_digest,
    }
    with pytest.raises(ConflictException):
        await service.confirm("issuer|owner", "north", preview.id, confirmation, "review")
    assert (await service.get("issuer|owner", "north", preview.id)).status == "stale"
    with pytest.raises(ConflictException):
        await service.confirm("issuer|owner", "north", preview.id, confirmation, "review")


async def test_stale_confirmation_and_changed_destination_do_not_enter_native_commit(curated):
    from pyfly.kernel import ConflictException

    service, catalog, destination, _ = curated
    preview = await service.preview("issuer|owner", "north", input_for(destination))
    service.native = SimpleNamespace(
        get=lambda: pytest.fail("Native commit must not be resolved before review admission")
    )
    with pytest.raises(ConflictException):
        await service.confirm(
            "issuer|owner",
            "north",
            preview.id,
            {"confirm": True, "expected_revision": 2, "authorization_digest": preview.authorization_digest},
            "wrong-revision",
        )
    await catalog.update("issuer|owner", "north", destination.id, {"name": "Changed destination"})
    with pytest.raises(ConflictException):
        await service.confirm(
            "issuer|owner",
            "north",
            preview.id,
            {"confirm": True, "expected_revision": 1, "authorization_digest": preview.authorization_digest},
            "stale-destination",
        )
