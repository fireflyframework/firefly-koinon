# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private account admission identities; never serialize these into public output."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=64)]
Revision = Annotated[int, Field(ge=0, le=9223372036854775807, strict=True)]


class AccountOperationIdentity(BaseModel):
    """Built by the authorized coordinator from verified account claims."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    tenant_id: Identifier
    account_key: bytes = Field(min_length=32, max_length=32, strict=True, repr=False)


class AccountOperationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["validation", "synchronization"]
    operation_id: Identifier
    revision: Revision
    generation: Revision = 0
    connection_id: Identifier
    connection_revision: Revision
    owner: str = Field(min_length=1, max_length=512)
    process_instance_id: Identifier

    @model_validator(mode="after")
    def validation_generation(self):
        if self.kind == "validation" and self.generation != 0:
            raise ValueError("validation generation must be zero")
        return self


class AccountOperationLease(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    identity: AccountOperationIdentity = Field(repr=False)
    operation: AccountOperationRequest = Field(repr=False)
    token: UUID = Field(repr=False)
    fence: int = Field(gt=0, strict=True)
    ticket: int = Field(gt=0, strict=True)
    started_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def bounded_deadline(self):
        if not 0 < (self.expires_at - self.started_at).total_seconds() <= 150:
            raise ValueError("account lease must last at most 150 seconds")
        return self


class AccountOperationBusy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    retry_after_seconds: int = Field(default=1, ge=1, le=30, strict=True)
