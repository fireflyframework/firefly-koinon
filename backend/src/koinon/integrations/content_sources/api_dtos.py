# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Credential-free public connection contracts, distinct from private provider grants."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from koinon.integrations.content_sources.dtos import Provider


class SourceAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Provider


class SourceAuthorizationCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: str = Field(min_length=1, max_length=64)
    state: SecretStr = Field(min_length=1, max_length=4096)
    code: SecretStr = Field(min_length=1, max_length=16384)


class SourceConnectionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class SourceAuthorizationOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    connection_id: str
    challenge_id: str
    authorization_url: str = Field(repr=False)
    expires_at: datetime


class SourceAccountOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: Provider
    subject: str
    tenant_id: str | None


class SourceConnectionOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    provider: Provider
    status: Literal["pending", "connected", "reconnect_required", "disconnected"]
    revision: int
    account: SourceAccountOutput | None


class SourceLocationOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    kind: Literal["site", "drive"]


class SourceLocationPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[SourceLocationOutput]
    next_cursor: str | None = Field(repr=False)


class SourceItemOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    item_id: str
    name: str
    kind: Literal["file", "folder", "shortcut"]
    version: str | None
    size_bytes: int | None
    mime_type: str
    parents: list[str]
    can_download: bool | None
    modified_at: str | None


class SourceFolderPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    folder: SourceItemOutput
    items: list[SourceItemOutput]
    next_cursor: str | None = Field(repr=False)
