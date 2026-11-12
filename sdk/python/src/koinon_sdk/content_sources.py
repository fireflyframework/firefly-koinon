# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/integrations/content_sources/api_dtos.py
SHA256: 1e2fdc39267c07e74f209d72afe67a29ed744d0c700690d0b426b694749feec0

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, SecretStr

from koinon_sdk._base import InputModel, ResponseModel

SourceProvider = Literal["sharepoint", "onedrive", "google_drive"]


class SourceProviderCapability(ResponseModel):
    provider: SourceProvider
    display_name: str
    consent_available: bool
    unavailable_reason: Literal["disabled", "not_configured"] | None


class SourceFormatCapability(ResponseModel):
    extension: str
    mode: Literal["document", "dataset"]


class SourceScheduleCapability(ResponseModel):
    min_interval_seconds: int
    max_interval_seconds: int
    calendar_timezones: Literal["iana"] = "iana"
    max_calendar_weekdays: Literal[7] = 7


class SourceCapabilitiesOutput(ResponseModel):
    accounts_available: bool
    inbound_only: Literal[True] = True
    synchronization_available: bool
    providers: list[SourceProviderCapability]
    modes: list[Literal["document", "dataset"]]
    formats: list[SourceFormatCapability]
    schedule: SourceScheduleCapability


class SourceAuthorizationInput(InputModel):
    provider: SourceProvider


class SourceAuthorizationCompletion(InputModel):
    challenge_id: str = Field(min_length=1, max_length=64)
    state: SecretStr = Field(min_length=1, max_length=4096)
    code: SecretStr = Field(min_length=1, max_length=16384)


class SourceConnectionRevision(InputModel):
    expected_revision: int = Field(ge=1)


class SourceAuthorizationOutput(ResponseModel):
    connection_id: str
    challenge_id: str
    authorization_url: str = Field(repr=False)
    callback_uri: str = Field(max_length=2048)
    expires_at: datetime


class SourceAccountOutput(ResponseModel):
    provider: SourceProvider
    subject: str
    tenant_id: str | None


class SourceConnectionOutput(ResponseModel):
    id: str
    provider: SourceProvider
    status: Literal["pending", "connected", "reconnect_required", "disconnected"]
    revision: int
    account: SourceAccountOutput | None
    display_name: str | None = Field(default=None, max_length=255)
    display_address: str | None = Field(default=None, max_length=320)
    display_address_verified: bool = False
    synchronization_available: bool = False


class SourceConnectionPage(ResponseModel):
    items: list[SourceConnectionOutput]
    next_cursor: str | None
    synchronization_available: bool = False


class SourceLocationOutput(ResponseModel):
    id: str
    name: str
    kind: Literal["site", "drive"]


class SourceLocationPage(ResponseModel):
    items: list[SourceLocationOutput]
    next_cursor: str | None = Field(repr=False)


class SourceItemOutput(ResponseModel):
    item_id: str
    name: str
    kind: Literal["file", "folder", "shortcut"]
    version: str | None
    size_bytes: int | None
    mime_type: str
    parents: list[str]
    can_download: bool | None
    modified_at: str | None


class SourceFolderPage(ResponseModel):
    folder: SourceItemOutput
    items: list[SourceItemOutput]
    next_cursor: str | None = Field(repr=False)
