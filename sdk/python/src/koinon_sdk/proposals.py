# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/assistants/proposal_dtos.py
SHA256: ea8dba65f50f7c078bd58d921b036d6200c78b30f84e1e56756a0e7d78e56b70

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel


class CatalogProposalPatch(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)


class CatalogProposalBefore(ResponseModel):
    name: str
    description: str


class CatalogProposal(ResponseModel):
    id: str
    run_id: str
    kind: Literal["catalog"] = "catalog"
    status: Literal["pending", "applied", "cancelled"]
    revision: int = Field(ge=1)
    asset_id: str
    before: CatalogProposalBefore
    changes: CatalogProposalPatch
    expected_catalog_digest: str = Field(pattern="^[a-f0-9]{64}$")
    created_at: datetime
    applied_at: datetime | None = None
    cancelled_at: datetime | None = None


class ProposalConfirmation(InputModel):
    confirm: Literal[True]
    expected_revision: int = Field(ge=1)


class ProposalRevision(InputModel):
    expected_revision: int = Field(ge=1)


class ProposalUpdate(ResponseModel):
    id: str
    status: Literal["applied", "cancelled"]
    revision: int = Field(ge=2)
