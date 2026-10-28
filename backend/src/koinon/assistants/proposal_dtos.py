# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


class CatalogProposalPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def selected_fields(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Propose a name or description as text")
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Choose a nonempty name")
        return self


class CatalogProposalBefore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    description: str


class CatalogProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    run_id: str
    kind: Literal["catalog"] = "catalog"
    status: Literal["pending", "applied", "cancelled"]
    revision: int = Field(ge=1)
    asset_id: str
    before: CatalogProposalBefore
    changes: CatalogProposalPatch
    expected_catalog_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    applied_at: datetime | None = None
    cancelled_at: datetime | None = None

    @field_serializer("changes")
    def selected_changes(self, value: CatalogProposalPatch):
        return value.model_dump(exclude_unset=True)


class ProposalConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True]
    expected_revision: int = Field(ge=1)

    @field_validator("confirm", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("Explicit confirmation is required")
        return value


class ProposalRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class ProposalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    status: Literal["applied", "cancelled"]
    revision: int = Field(ge=2)
