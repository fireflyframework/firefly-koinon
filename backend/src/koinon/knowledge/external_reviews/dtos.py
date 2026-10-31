# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator

from koinon.knowledge.curated.dtos import (
    Action,
    Frozen,
    Identifier,
    KnowledgeContent,
    KnowledgeIntent,
    KnowledgeIntentInput,
    Sha256,
)


class ExternalReviewInput(Frozen):
    action: Action
    destination_id: Identifier
    target_item_id: Identifier | None = None
    expected_version: int | None = Field(default=None, ge=1)
    content: KnowledgeContent
    source_receipt_ids: tuple[Identifier, ...] = Field(default=(), max_length=32)

    @field_validator("source_receipt_ids")
    @classmethod
    def distinct(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Select distinct source read receipts")
        return value

    def intent(self):
        return KnowledgeIntentInput.model_validate(
            {
                **self.model_dump(mode="json", exclude={"source_receipt_ids"}),
                "origin": {"kind": "external_proposal", "source_receipt_ids": self.source_receipt_ids},
            }
        )


class ExternalReviewView(Frozen):
    id: Identifier
    review: KnowledgeIntent
    status: Literal["preview", "committing", "committed", "cancelled", "stale", "unresolved"]
    expires_at: AwareDatetime


class ExternalReviewChallenge(Frozen):
    """Private component-channel payload; never a public API response schema."""

    review: ExternalReviewView
    nonce: str = Field(min_length=43, max_length=43)


class ExternalReviewDecision(Frozen):
    expected_revision: int = Field(ge=1)
    authorization_digest: Sha256
    nonce: str = Field(min_length=43, max_length=43)
