# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/sharing/dtos.py
SHA256: 86543c76b1cfb1cb8ea1a8687ddd9323cffeed23dc4f3e97cf75a1958a57e072

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field

from koinon_sdk.evidence import ConversationMessage, Frozen, Identifier, Revision, SourceReference
from koinon_sdk.exports import Input, MessageSelection


class ShareReviewInput(MessageSelection):
    pass


class ShareCreate(Input):
    review_id: Identifier
    expected_revision: Revision
    expires_in_hours: int = Field(default=24, ge=1, le=168)
    recipient_policy: Literal["organization_current_acl"] = "organization_current_acl"


class ShareReview(Frozen):
    id: Identifier
    revision: Revision
    title: str
    message_count: int
    source_count: int
    messages: tuple[ConversationMessage, ...]
    sources: tuple[SourceReference, ...]
    source_manifest_complete: bool
    recipient_policy: Literal["organization_current_acl"] = "organization_current_acl"
    omissions: tuple[str, ...] = ()
    expires_at: AwareDatetime


class Share(Frozen):
    id: Identifier
    title: str
    revision: Revision
    status: Literal["active", "revoked", "expired"]
    recipient_policy: Literal["organization_current_acl"] = "organization_current_acl"
    created_at: AwareDatetime
    expires_at: AwareDatetime
    revoked_at: AwareDatetime | None = None


class SharedConversation(Frozen):
    share: Share
    messages: tuple[ConversationMessage, ...]
    sources: tuple[SourceReference, ...]
    source_manifest_complete: bool


class SharePage(Frozen):
    items: tuple[Share, ...]
    total: int
    page: int
    page_size: int
    pages: int
