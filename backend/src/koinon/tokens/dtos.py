# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class TokenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    tenant_id: str = Field(min_length=1, max_length=64)
    scopes: list[str] = Field(min_length=1, max_length=64)
    workspace_ids: list[str] | None = Field(default=None, max_length=128)
    asset_ids: list[str] | None = Field(default=None, max_length=128)
    expires_at: AwareDatetime
