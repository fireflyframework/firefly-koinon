# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from koinon.catalog.dtos import Role


class InvitationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role
    workspace_id: str | None = Field(default=None, max_length=64)
    expires_in_hours: int = Field(default=24, ge=1, le=168)
    label: str = Field(default="", max_length=120)


class InvitationToken(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr = Field(min_length=40, max_length=128)


class InvitationOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    tenant_id: str
    workspace_id: str | None
    role: Role
    label: str
    created_by: str
    created_at: datetime
    expires_at: datetime
    status: Literal["pending", "accepted", "expired", "revoked"]
    accepted_at: datetime | None = None
    accepted_by: str | None = None


class InvitationCreated(BaseModel):
    model_config = ConfigDict(frozen=True)
    invitation: InvitationOutput
    token: SecretStr


class InvitationPreview(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    tenant_id: str
    tenant_name: str
    workspace_id: str | None
    workspace_name: str | None
    role: Role
    expires_at: datetime


class InvitationPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[InvitationOutput]
    total: int
    page: int
    page_size: int
    pages: int
