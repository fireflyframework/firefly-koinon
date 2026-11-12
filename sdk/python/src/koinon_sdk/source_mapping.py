# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/integrations/content_sources/mapping_dtos.py
SHA256: 1306ba3c335a3e0f67c4b56e5b8c8fd2cb6889d3c9a1bbb8eb1a8cfe3344ac86

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel
from koinon_sdk.bulk import BulkDestination, Digest
from koinon_sdk.evidence import Identifier


class ReplacementMemberInput(InputModel):
    new_locator: str = Field(strict=True, min_length=1, max_length=2048)
    previous_table_id: str | None


class ReplacementResolutionInput(InputModel):
    object_id: Identifier
    remote_version: str = Field(strict=True, min_length=1, max_length=1024)
    content_sha256: Digest
    baseline_sha256: Digest
    new_locator_set_sha256: Digest
    replacements: list[ReplacementMemberInput] = Field(min_length=1, max_length=16)
    removed_table_ids: list[str] = Field(default_factory=list[str], max_length=16)


class ManualSchedule(InputModel):
    kind: Literal["manual"] = "manual"


class IntervalSchedule(InputModel):
    kind: Literal["interval"]
    seconds: int = Field(strict=True, ge=900, le=604800)


class CalendarSchedule(InputModel):
    kind: Literal["calendar"]
    timezone: str = Field(strict=True, min_length=1, max_length=255)
    time: str = Field(strict=True, pattern="^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    weekdays: list[Annotated[int, Field(strict=True, ge=1, le=7)]] = Field(
        default_factory=lambda: list(range(1, 8)), min_length=1, max_length=7
    )


SourceSchedule = Annotated[ManualSchedule | IntervalSchedule | CalendarSchedule, Field(discriminator="kind")]


class MappingReviewInput(InputModel):
    connection_id: Identifier
    drive_id: str = Field(strict=True, min_length=1, max_length=1024)
    root_id: str = Field(strict=True, min_length=1, max_length=1024)
    destination: BulkDestination
    recursive: bool = Field(strict=True)
    removal_policy: Literal["retire", "pause_for_review"]
    schema_version: Literal[1] = 1
    mode: Literal["document", "dataset"] = "document"
    hierarchy: Literal["preserve", "flatten"] = "preserve"
    excluded_ids: list[str] = Field(default_factory=list[str], max_length=1000)
    formats: list[str] = Field(default_factory=lambda: [".pdf", ".txt", ".md"], min_length=1, max_length=100)
    schedule: SourceSchedule = Field(default_factory=ManualSchedule)
    replacement_resolutions: list[ReplacementResolutionInput] = Field(
        default_factory=list[ReplacementResolutionInput], max_length=16
    )


class MappingReviewOutput(ResponseModel):
    id: str
    revision: int
    status: Literal["reviewed"] = "reviewed"
    expires_at: datetime
