# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["viewer", "analyst", "editor", "operator", "admin"]


Status = Literal["ready", "draft", "pending", "disabled", "archived", "error"]


class CatalogCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    parent_id: str | None = Field(default=None, max_length=64)
    description: str = Field(default="", max_length=4000)
    metadata: dict = Field(default_factory=dict)


class CatalogPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    metadata: dict | None = None


class MemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=512)
    role: Role
    workspace_id: str | None = Field(default=None, max_length=64)


class MemberPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role | None = None
    active: bool | None = None


class MemberOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    subject: str
    tenant_id: str
    workspace_id: str | None
    role: Role
    active: bool
    managed: bool = False
    origin: Literal["manual", "corporate"] = "manual"
    source_id: str | None = None
    source_name: str | None = None
    expires_at: datetime | None = None


class MemberActor(BaseModel):
    model_config = ConfigDict(frozen=True)
    subject: str
    display_name: str
    avatar_data_url: str | None = None
    avatar_version: str | None = None


class MembershipPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[MemberOutput]
    actors: dict[str, MemberActor]
    total: int
    page: int
    page_size: int
    pages: int
