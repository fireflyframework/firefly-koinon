# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/knowledge/external_reviews/dtos.py
SHA256: a69e7062306860b557d8b932967a74d1c1659825dfeae788aaa80de8e511d862

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field

from koinon_sdk._base import InputModel
from koinon_sdk.curated import Action, Frozen, Identifier, KnowledgeContent, KnowledgeIntent, Sha256


class ExternalReviewInput(InputModel):
    action: Action
    destination_id: Identifier
    target_item_id: Identifier | None = None
    expected_version: int | None = Field(default=None, ge=1)
    content: KnowledgeContent
    source_receipt_ids: tuple[Identifier, ...] = Field(default=(), max_length=32)


class ExternalReviewView(Frozen):
    id: Identifier
    review: KnowledgeIntent
    status: Literal["preview", "committing", "committed", "cancelled", "stale", "unresolved"]
    expires_at: AwareDatetime


class ExternalReviewDecision(InputModel):
    expected_revision: int = Field(ge=1)
    authorization_digest: Sha256
    nonce: str = Field(min_length=43, max_length=43)
