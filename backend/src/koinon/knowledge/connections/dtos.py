# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: Literal["documents", "structured"]
    role: str = Field(min_length=1, max_length=64)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=64)
    mode: Literal["provider", "current_agent"] = "provider"
    provider_id: str | None = Field(default=None, min_length=1, max_length=64)
    model_id: str | None = Field(default=None, min_length=1, max_length=255)
    model_options: dict = Field(default_factory=dict)
    dimensions: int | None = Field(default=None, ge=1, le=4096, strict=True)
    storage_dimensions: int | None = Field(default=None, ge=1, le=4096, strict=True)
    space_id: str | None = Field(default=None, min_length=1, max_length=256)
    enabled: bool = True
    expected_revision: int | None = Field(default=None, ge=1, strict=True)
