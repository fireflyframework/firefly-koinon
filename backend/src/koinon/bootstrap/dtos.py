# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


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


class BootstrapContactInput(BaseModel):
    """Operator observation, never an authentication assertion or a recipient-supplied address."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=1, max_length=64)
    issuer: str = Field(min_length=1, max_length=512)
    client_id: str = Field(min_length=1, max_length=255)
    entra_tenant_id: UUID
    object_id: UUID
    email: str = Field(min_length=3, max_length=320, repr=False)
    display_name: str = Field(min_length=1, max_length=120)
    observed_at: AwareDatetime
    source: Literal["microsoft_graph_v1"]
    account_enabled: bool = Field(strict=True)
    user_type: Literal["Member"]

    @field_validator("email")
    @classmethod
    def valid_address(cls, value):
        from koinon.communications.directory import delivery_address

        parsed = delivery_address(value)
        if parsed is None:
            raise ValueError("Supply the verified directory delivery address")
        return parsed

    @field_validator("display_name")
    @classmethod
    def safe_label(cls, value):
        if value != value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Supply a safe directory display name")
        return value

    @model_validator(mode="after")
    def enabled_member(self):
        if not self.account_enabled:
            raise ValueError("Only enabled directory members can receive bootstrap welcome")
        return self
