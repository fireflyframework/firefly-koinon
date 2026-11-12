# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/integrations/content_sources/read_dtos.py
SHA256: 110960ab7031bbd0015f0346e5e7ba70eac133397a7e09060ec16307e1b0d8c5

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal
from uuid import UUID

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel


class ReaderSourceSelection(InputModel):
    provider: Literal["sharepoint", "onedrive", "google_drive"]
    external_tenant: str | None = Field(default=None, min_length=1, max_length=1024)
    connection_id: str = Field(min_length=1, max_length=64)


class ReaderSelectionInput(InputModel):
    expected_revision: int = Field(ge=0)
    operation_id: UUID
    connections: list[ReaderSourceSelection] = Field(max_length=100)


class ReaderSelectionOutput(ResponseModel):
    revision: int
    connections: tuple[ReaderSourceSelection, ...]


class ReaderReadInput(InputModel):
    reader_source_connections: list[ReaderSourceSelection] | None = Field(default=None, max_length=100)


class ReaderPageInput(ReaderReadInput):
    page: int = Field(default=1, ge=1, le=100000, strict=True)
    page_size: int = Field(default=25, ge=1, le=100, strict=True)
