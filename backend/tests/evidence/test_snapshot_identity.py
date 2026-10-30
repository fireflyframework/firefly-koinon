# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from hashlib import sha256
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException, ServiceUnavailableException
from test_evidence_reviews import reviews as reviews

from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository
from koinon.evidence.dtos import ConversationSnapshot
from koinon.evidence.repositories import EvidenceReviewRepository
from koinon.evidence.reviews import digest
from koinon.exports.dtos import ConversationExportInput, ExportCreate
from koinon.exports.service import KnowledgeExports
from koinon.organization_branding.dtos import BrandingValues, OrganizationBrandingInput, encode_branding
from koinon.organization_branding.service import OrganizationBrandingService
from koinon.sharing.dtos import ShareCreate, ShareReviewInput
from koinon.sharing.service import ConversationShares


async def configure(context, name):
    members = context.get_bean(MembershipRepository)
    owner = await members.find_by_id("owner")
    owner.role = "admin"
    await members.save(owner)
    branding = context.get_bean(OrganizationBrandingService)
    revision = (await branding.get("owner", "north")).revision
    return await branding.update("owner", "north", OrganizationBrandingInput(
        expected_revision=revision,
        branding=BrandingValues(product_name=name, assistant_name=name + " helper"),
    ))


@pytest.mark.parametrize("purpose", ["export", "share"])
async def test_new_review_binds_authorized_identity_without_changing_conversation_revision(reviews, purpose):
    service, _, context = reviews
    configured = await configure(context, "North")
    body = ShareReviewInput(thread_id="t", message_ids=["m"])
    row = await service.conversation("owner", "north", body, purpose=purpose)
    identity = row.snapshot_json.get("identity")
    assert identity == {
        "product_name": "North", "assistant_name": "North helper", "branding_revision": 1,
        "branding_origin": "organization", "branding_sha256": sha256(
            encode_branding(configured.branding).encode("ascii")
        ).hexdigest(),
    }
    assert row.snapshot_json["revision"] == "a" * 64
    assert row.revision == digest({"request": row.request_json, "snapshot": row.snapshot_json})
    assert "logo" not in json.dumps(identity) and "tenant_id" not in identity


async def test_share_review_and_read_keep_saved_identity_after_branding_changes(reviews):
    _, _, context = reviews
    await configure(context, "Before")
    shares = context.get_bean(ConversationShares)
    preview = await shares.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
    assert preview.model_dump()["identity"]["assistant_name"] == "Before helper"
    await configure(context, "After")
    shared = await shares.create("owner", "north", ShareCreate(
        review_id=preview.id, expected_revision=preview.revision,
    ))
    value = await shares.read("owner", "north", shared.id)
    assert value.model_dump()["identity"] == preview.model_dump()["identity"]


async def test_export_keeps_snapshot_identity_in_preview_and_download_after_reset(reviews):
    _, _, context = reviews
    await configure(context, "Before")
    exports = context.get_bean(KnowledgeExports)
    preview = await exports.preview("owner", "north", ConversationExportInput(
        kind="conversation", thread_id="t", message_ids=["m"], format="json",
    ))
    assert preview.model_dump()["identity"]["product_name"] == "Before"
    await context.get_bean(OrganizationBrandingService).reset("owner", "north", 1)
    exported = await exports.create("owner", "north", ExportCreate(
        review_id=preview.id, expected_revision=preview.revision,
    ))
    data = json.loads((await exports.download("owner", "north", exported.id)).content)
    assert data["identity"] == preview.model_dump()["identity"]
    assert data["messages"][0]["display_name"] == "Before helper"


async def test_historical_review_claim_keeps_old_hash_and_unknown_identity(reviews):
    service, _, context = reviews
    body = ShareReviewInput(thread_id="t", message_ids=["m"])
    row = await service.conversation("owner", "north", body, purpose="share")
    old = {key: value for key, value in row.snapshot_json.items() if key != "identity"}
    row.snapshot_json = old
    row.revision = digest({"request": row.request_json, "snapshot": old})
    await context.get_bean(EvidenceReviewRepository).save(row)
    await configure(context, "Today")
    claimed = await service.claim("owner", "north", row.id, row.revision, purpose="share")
    assert claimed.snapshot_json == old
    assert ConversationSnapshot.model_validate(old).model_dump().get("identity") is None


async def test_branding_failure_never_creates_a_review_without_identity(reviews, monkeypatch):
    service, _, context = reviews
    branding = context.get_bean(OrganizationBrandingService)
    monkeypatch.setattr(branding, "get", AsyncMock(side_effect=ServiceUnavailableException("Unavailable")))
    with pytest.raises(ServiceUnavailableException):
        await service.conversation("owner", "north", ShareReviewInput(
            thread_id="t", message_ids=["m"],
        ), purpose="share")
    assert await context.get_bean(EvidenceReviewRepository).active_count("owner", "north") == 0


async def test_branding_capture_still_denies_foreign_organization(reviews):
    _, _, context = reviews
    with pytest.raises(AccessDenied):
        await context.get_bean(OrganizationBrandingService).get("owner", "foreign")


async def test_identity_does_not_disable_changed_content_review_fence(reviews):
    service, snapshot, context = reviews
    row = await service.conversation("owner", "north", ShareReviewInput(
        thread_id="t", message_ids=["m"],
    ), purpose="share")
    await configure(context, "Changed")
    snapshot.revision = "b" * 64
    with pytest.raises(ConflictException):
        await service.claim("owner", "north", row.id, row.revision, purpose="share")
