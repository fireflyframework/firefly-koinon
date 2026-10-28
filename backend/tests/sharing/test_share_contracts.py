# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError

from koinon.sharing.dtos import ShareCreate, ShareReviewInput


def test_share_accepts_only_authenticated_current_acl_with_bounded_lifetime():
    share = ShareCreate(review_id="r", expected_revision="a" * 64)
    assert share.expires_in_hours == 24 and share.recipient_policy == "organization_current_acl"
    with pytest.raises(ValidationError):
        ShareCreate(review_id="r", expected_revision="a" * 64, recipient_policy="anonymous")
    with pytest.raises(ValidationError):
        ShareCreate(review_id="r", expected_revision="a" * 64, expires_in_hours=169)


def test_share_review_cannot_accept_model_authored_snapshot_or_attachment_bytes():
    with pytest.raises(ValidationError):
        ShareReviewInput(thread_id="t", message_ids=["m"], text="forged content")
    with pytest.raises(ValidationError):
        ShareReviewInput(thread_id="t", message_ids=["m"], attachment_bytes="private")
