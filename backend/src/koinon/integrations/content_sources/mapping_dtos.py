# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private review contracts; a reviewed mapping is not an enabled synchronization."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from koinon.integrations.content_sources.dtos import bounded
from koinon.knowledge.bulk.dtos import BulkDestination, Digest, Identifier, Input, Output

VALIDATION_MAX_LIFETIME_SECONDS = 8 * 60 * 60


def canonical_table_id(value: str) -> str:
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Use a canonical lowercase table UUID")
    return value


class ReplacementMemberInput(Input):
    new_locator: str = Field(strict=True, min_length=1, max_length=2048)
    previous_table_id: str | None

    @field_validator("new_locator")
    @classmethod
    def bounded_locator(cls, value: str) -> str:
        bounded(value, limit=2048)
        if len(value.encode("utf-8")) > 2048:
            raise ValueError("Parser locators cannot exceed 2048 UTF-8 bytes")
        return value

    @field_validator("previous_table_id")
    @classmethod
    def table_id(cls, value: str | None) -> str | None:
        return canonical_table_id(value) if value is not None else None


class ReplacementResolutionInput(Input):
    object_id: Identifier
    remote_version: str = Field(strict=True, min_length=1, max_length=1024)
    content_sha256: Digest
    baseline_sha256: Digest
    new_locator_set_sha256: Digest
    replacements: list[ReplacementMemberInput] = Field(min_length=1, max_length=16)
    removed_table_ids: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("remote_version")
    @classmethod
    def version(cls, value: str) -> str:
        return bounded(value)

    @field_validator("removed_table_ids")
    @classmethod
    def removed(cls, value: list[str]) -> list[str]:
        return [canonical_table_id(identifier) for identifier in value]

    @model_validator(mode="after")
    def unique_members(self):
        locators = [member.new_locator for member in self.replacements]
        retained = [member.previous_table_id for member in self.replacements if member.previous_table_id]
        identities = [*retained, *self.removed_table_ids]
        if len(set(locators)) != len(locators) or len(set(identities)) != len(identities):
            raise ValueError("Every locator and previous table must occur exactly once")
        return self


class ManualSchedule(Input):
    kind: Literal["manual"] = "manual"


class IntervalSchedule(Input):
    kind: Literal["interval"]
    seconds: int = Field(strict=True, ge=900, le=604800)


class CalendarSchedule(Input):
    kind: Literal["calendar"]
    timezone: str = Field(strict=True, min_length=1, max_length=255)
    time: str = Field(strict=True, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    weekdays: list[Annotated[int, Field(strict=True, ge=1, le=7)]] = Field(
        default_factory=lambda: list(range(1, 8)), min_length=1, max_length=7
    )

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use an installed IANA timezone") from None
        return value

    @field_validator("weekdays")
    @classmethod
    def unique_weekdays(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("Weekdays must be unique")
        return sorted(value)


SourceSchedule = Annotated[ManualSchedule | IntervalSchedule | CalendarSchedule, Field(discriminator="kind")]


class MappingReviewInput(Input):
    connection_id: Identifier
    drive_id: str = Field(strict=True, min_length=1, max_length=1024)
    root_id: str = Field(strict=True, min_length=1, max_length=1024)
    destination: BulkDestination
    recursive: bool = Field(strict=True)
    removal_policy: Literal["retire", "pause_for_review"]
    schema_version: Literal[1] = 1
    mode: Literal["document", "dataset"] = "document"
    hierarchy: Literal["preserve", "flatten"] = "preserve"
    excluded_ids: list[str] = Field(default_factory=list, max_length=1000)
    formats: list[str] = Field(default_factory=lambda: [".pdf", ".txt", ".md"], min_length=1, max_length=100)
    schedule: SourceSchedule = Field(default_factory=ManualSchedule)
    replacement_resolutions: list[ReplacementResolutionInput] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def bounded_resolutions(self):
        identities = [item.object_id for item in self.replacement_resolutions]
        if len(set(identities)) != len(identities) or identities and self.mode != "dataset":
            raise ValueError("Replacement resolutions require unique dataset objects")
        encoded = json.dumps(
            [value.model_dump(mode="json") for value in self.replacement_resolutions],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        if len(encoded.encode("utf-8")) > 256 * 1024:
            raise ValueError("Replacement resolutions exceed their bounded review size")
        return self

    @field_validator("excluded_ids")
    @classmethod
    def valid_exclusions(cls, value: list[str]) -> list[str]:
        for identifier in value:
            bounded(identifier)
        if len(set(value)) != len(value):
            raise ValueError("Excluded identifiers must be unique")
        return sorted(value)

    @field_validator("formats")
    @classmethod
    def valid_formats(cls, value: list[str]) -> list[str]:
        import re

        if len(set(value)) != len(value) or any(
            not re.fullmatch(r"\.[a-z0-9]+(?:\.[a-z0-9]+)?", extension) for extension in value
        ):
            raise ValueError("Use unique lowercase file extensions")
        return sorted(value)

    @field_validator("drive_id", "root_id")
    @classmethod
    def valid_remote_identifier(cls, value: str) -> str:
        return bounded(value, limit=1024)


class MappingReviewOutput(Output):
    id: str
    revision: int
    status: Literal["reviewed"] = "reviewed"
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class MappingCandidate:
    id: str
    revision: int
    root_id: str
    request_sha256: str
    recursive: bool
    status: str
