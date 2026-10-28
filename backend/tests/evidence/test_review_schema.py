# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon.evidence.entities import EvidenceReview
from koinon.exports.entities import ExportRecord
from koinon.sharing.entities import ConversationShare


def test_review_and_artifacts_reference_private_snapshots_without_tokens_or_attachment_columns():
    review = EvidenceReview.__table__
    assert {
        "tenant_id",
        "owner_subject",
        "request_json",
        "snapshot_json",
        "manifest_json",
        "expires_at",
        "consumed_at",
    } <= set(review.columns.keys())
    for model in (EvidenceReview, ExportRecord, ConversationShare):
        fields = set(model.__table__.columns.keys())
        assert not fields & {"token", "attachment_bytes", "storage_url", "public_url", "email"}
    assert ExportRecord.__table__.c.review_id.foreign_keys
    assert ConversationShare.__table__.c.review_id.foreign_keys
