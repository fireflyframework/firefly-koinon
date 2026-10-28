# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/exports/dtos.py
SHA256: d8939718d9d9ba63942129e1e00eaea6d80888d0c64d9e179d6e8c3ff3c368f7

Server authorization and semantic validation remain authoritative.
"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, RootModel

from koinon_sdk._base import InputModel
from koinon_sdk.evidence import (
    ConversationMessage,
    Frozen,
    Identifier,
    Revision,
    SourceReference,
    StoredResult,
)


class Input(InputModel):
    pass


class MessageSelection(Input):
    thread_id: Identifier
    message_ids: list[Identifier] = Field(min_length=1, max_length=200)


class ConversationExportInput(MessageSelection):
    kind: Literal["conversation"]
    format: Literal["markdown", "json"]
    include_evidence: bool = True


class QueryResultExportInput(Input):
    kind: Literal["query_result"]
    dataset_id: Identifier
    query_id: Identifier
    format: Literal["parquet", "csv", "jsonl"]
    csv_mode: Literal["spreadsheet_safe", "exact"] = "spreadsheet_safe"


ExportReviewInput = Annotated[ConversationExportInput | QueryResultExportInput, Field(discriminator="kind")]


class ExportReviewRequest(RootModel[ExportReviewInput]):
    pass


class ExportCreate(Input):
    review_id: Identifier
    expected_revision: Revision


class ExportReview(Frozen):
    id: Identifier
    revision: Revision
    kind: Literal["conversation", "query_result"]
    format: Literal["markdown", "json", "parquet", "csv", "jsonl"]
    title: str
    message_count: int = Field(ge=0, le=200)
    source_count: int = Field(ge=0, le=500)
    row_count: int | None = Field(default=None, ge=0)
    row_cap: int | None = Field(default=None, ge=1)
    truncated: bool | None = None
    completeness: Literal["selected_messages", "bounded", "unknown"]
    messages: tuple[ConversationMessage, ...] = ()
    sources: tuple[SourceReference, ...] = ()
    source_manifest_complete: bool = False
    result: StoredResult | None = None
    omissions: tuple[str, ...] = ()
    expires_at: AwareDatetime


class Export(Frozen):
    id: Identifier
    kind: Literal["conversation", "query_result"]
    format: Literal["markdown", "json", "parquet", "csv", "jsonl"]
    title: str
    status: Literal["ready", "cancelled", "expired"]
    revision: Revision
    completeness: Literal["selected_messages", "bounded", "unknown"]
    row_count: int | None = None
    truncated: bool | None = None
    created_at: AwareDatetime
    expires_at: AwareDatetime


class ExportPage(Frozen):
    items: tuple[Export, ...]
    total: int
    page: int
    page_size: int
    pages: int
