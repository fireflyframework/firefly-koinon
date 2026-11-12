# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Credential-free public connection contracts, distinct from private provider grants."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

SourceProvider = Literal["sharepoint", "onedrive", "google_drive"]


class SourceProviderCapability(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: SourceProvider
    display_name: str
    consent_available: bool
    unavailable_reason: Literal["disabled", "not_configured"] | None


class SourceFormatCapability(BaseModel):
    model_config = ConfigDict(frozen=True)
    extension: str
    mode: Literal["document", "dataset"]


class SourceScheduleCapability(BaseModel):
    model_config = ConfigDict(frozen=True)
    min_interval_seconds: int
    max_interval_seconds: int
    calendar_timezones: Literal["iana"] = "iana"
    max_calendar_weekdays: Literal[7] = 7


class SourceValidationLimits(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_scan_items: int
    max_active_per_owner: int
    max_active_per_tenant: int
    max_records_per_tenant: int
    max_retained_bytes_per_tenant: int
    max_lifetime_seconds: int
    lifetime_limited_by_session: Literal[True] = True


class SourceCapabilitiesOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    accounts_available: bool
    inbound_only: Literal[True] = True
    synchronization_available: bool
    providers: list[SourceProviderCapability]
    modes: list[Literal["document", "dataset"]]
    formats: list[SourceFormatCapability]
    schedule: SourceScheduleCapability
    validation_limits: SourceValidationLimits


class SourceAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: SourceProvider


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
    callback_uri: str = Field(max_length=2048)
    expires_at: datetime


class SourceAccountOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: SourceProvider
    subject: str
    tenant_id: str | None


class SourceConnectionOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    provider: SourceProvider
    status: Literal["pending", "connected", "reconnect_required", "disconnected"]
    revision: int
    account: SourceAccountOutput | None
    display_name: str | None = Field(default=None, max_length=255)
    display_address: str | None = Field(default=None, max_length=320)
    display_address_verified: bool = False
    synchronization_available: bool = False


class SourceConnectionPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[SourceConnectionOutput]
    next_cursor: str | None
    synchronization_available: bool = False


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
