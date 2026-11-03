# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private review contracts; a reviewed mapping is not an enabled synchronization."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from koinon.integrations.content_sources.dtos import bounded
from koinon.knowledge.bulk.dtos import BulkDestination, Identifier, Input, Output


class MappingReviewInput(Input):
    connection_id: Identifier
    drive_id: str = Field(strict=True, min_length=1, max_length=1024)
    root_id: str = Field(strict=True, min_length=1, max_length=1024)
    destination: BulkDestination
    recursive: bool = Field(strict=True)
    removal_policy: Literal["retire", "pause_for_review"]

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
