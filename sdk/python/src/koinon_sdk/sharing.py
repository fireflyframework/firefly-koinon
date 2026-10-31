# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/sharing/dtos.py
SHA256: ed1ac376f2a612ee93c01ea25ab0290513f00c6ad1b8d18410dbef95a9c414fa

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field

from koinon_sdk.evidence import (
    ConversationIdentity,
    ConversationMessage,
    Frozen,
    Identifier,
    Revision,
    SourceReference,
)
from koinon_sdk.exports import Input, MessageSelection


class ShareReviewInput(MessageSelection):
    pass


class ShareCreate(Input):
    review_id: Identifier
    expected_revision: Revision
    expires_in_hours: int = Field(default=24, ge=1, le=168)
    recipient_policy: Literal["organization_current_acl"] = "organization_current_acl"
    include_remembered_context: bool = Field(default=False, strict=True)


class ShareReview(Frozen):
    id: Identifier
    revision: Revision
    title: str
    message_count: int
    source_count: int
    messages: tuple[ConversationMessage, ...]
    sources: tuple[SourceReference, ...]
    source_manifest_complete: bool
    remembered_context_present: bool = False
    recipient_policy: Literal["organization_current_acl"] = "organization_current_acl"
    omissions: tuple[str, ...] = ()
    expires_at: AwareDatetime
    identity: ConversationIdentity | None = None


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
    identity: ConversationIdentity | None = None


class SharePage(Frozen):
    items: tuple[Share, ...]
    total: int
    page: int
    page_size: int
    pages: int
