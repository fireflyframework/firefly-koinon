# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Source mapping collection projections and immutable operation unions."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from koinon_sdk._base import ResponseModel
from koinon_sdk.source_sync import SourceMappingPresentation, SourceRunOutput


class SourceMappingSummary(ResponseModel):
    id: str
    status: Literal["reviewed", "active", "paused", "reconnect_required", "retired"]
    connection_id: str
    policy_revision: int | None
    latest_review_revision: int
    control_revision: int | None
    next_run_at: datetime | None
    presentation: SourceMappingPresentation


class SourceMappingPage(ResponseModel):
    items: list[SourceMappingSummary] = Field(max_length=100)
    next_cursor: str | None


class SourceRunPage(ResponseModel):
    items: list[SourceRunOutput] = Field(max_length=100)
    next_cursor: str | None
