# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/sharing/dtos.py
SHA256: b78892ecdb13a174174367d6e06472569ce400d0b1213879569c3350b64cb08c

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
from koinon_sdk.reader_sources import ReaderSourceSelection


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


class ShareBrowseInput(Input):
    q: str = Field(default="", max_length=512)
    status: Literal["all", "active", "revoked", "expired"] = "all"
    page_size: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=128)
    reader_source_connections: list[ReaderSourceSelection] | None = Field(default=None, max_length=100)


class ShareBrowsePage(Frozen):
    items: tuple[Share, ...]
    next_cursor: str | None = None
    total: None = None
    total_is_exact: Literal[False] = False
