# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class BootstrapIdentityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_id: UUID
    role: Literal["admin"]
    expires_at: AwareDatetime


class BootstrapSeedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issuer: str = Field(min_length=1, max_length=512)
    client_id: str = Field(min_length=1, max_length=255)
    entra_tenant_id: UUID
    grants: list[BootstrapIdentityInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_identities(self):
        if len({row.object_id for row in self.grants}) != len(self.grants):
            raise ValueError("Choose each immutable directory identity once")
        return self
