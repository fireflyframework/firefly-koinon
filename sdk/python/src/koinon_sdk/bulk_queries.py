# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/knowledge/bulk_queries/dtos.py
SHA256: cdd8513cc50a99373a5a2fd253586ed2bff6320aa6fd3bb6857ca9f03201be89

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, JsonValue

from koinon_sdk._base import InputModel, ResponseModel
from koinon_sdk.models import ClarificationFrame, UsageSummary
from koinon_sdk.organization_knowledge import OrganizationKnowledgeSnapshot

Identifier = Annotated[str, Field(strict=True, min_length=1, max_length=64)]
QueryItemStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "reconciling"]
QueryBatchStatus = Literal["queued", "running", "succeeded", "partial", "failed", "cancelled", "reconciling"]


class Input(InputModel):
    pass


class Output(ResponseModel):
    pass


class QueryManifestItem(Input):
    client_item_id: Identifier
    dataset_id: Identifier
    question: str = Field(strict=True, min_length=1, max_length=8000)


class QueryBatchCreate(Input):
    workspace_id: Identifier
    processing_policy: Literal["independent_nl_v1"] = "independent_nl_v1"
    items: list[QueryManifestItem] = Field(min_length=1, max_length=20)


class QueryBatchAction(Input):
    expected_revision: int = Field(strict=True, ge=1, le=2147483647)


class QueryBatchCapabilities(Output):
    configured: bool
    processing_policy: Literal["independent_nl_v1"] = "independent_nl_v1"
    automatic_unknown_replay: Literal[False] = False
    shared_conversation: Literal[False] = False
    connection_mode: Literal["explicit_provider"] = "explicit_provider"
    max_queries: int = 20
    max_question_characters: int = 8000
    max_question_bytes_per_batch: int = 65536
    max_result_bytes: int = 1048576


class BatchQueryOutcome(Output):
    query_id: UUID
    execution_status: Literal["OK", "REFINED_OK", "FAILED", "REJECTED_BY_FIREWALL"] | None
    sql: str | None = Field(default=None, max_length=65536)
    preview: list[dict[str, JsonValue]] | None = Field(default=None, max_length=100)
    row_count: int | None = Field(default=None, ge=0, le=2147483647)
    elapsed_ms: int | None = Field(default=None, ge=0, le=3600000)
    truncated: bool = False
    chart_hint: Literal["line", "bar", "table", "pie", "none"] | None = None
    explanation: str | None = Field(default=None, max_length=65536)
    clarification: ClarificationFrame | None = None
    grounded_summary: dict[str, JsonValue] | None = None
    usage: UsageSummary | None = None
    snapshot_pins: dict[str, str] = Field(default_factory=dict[str, str], max_length=128)
    knowledge_settings_snapshot: OrganizationKnowledgeSnapshot


class QueryBatchView(Output):
    id: str
    tenant_id: str
    workspace_id: str
    status: QueryBatchStatus
    revision: int = Field(ge=1, le=2147483647)
    total_items: int = Field(ge=1, le=20)
    counts: dict[QueryItemStatus, int]
    cancellation_requested: bool
    created_at: datetime
    expires_at: datetime


class QueryBatchItemView(Output):
    id: str
    client_item_id: str
    dataset_id: str
    question: str
    status: QueryItemStatus
    job_id: str
    error_code: str | None = None
    query_id: UUID | None = None


class QueryBatchResult(Output):
    batch_id: str
    item_id: str
    status: QueryItemStatus
    result: BatchQueryOutcome | None = None
    error_code: str | None = None


class QueryBatchPage(Output):
    items: list[QueryBatchView]
    total: int
    page: int
    page_size: int
    pages: int


class QueryBatchItemPage(Output):
    items: list[QueryBatchItemView]
    total: int
    page: int
    page_size: int
    pages: int


class QueryBatchCancellation(Output):
    batch_id: str
    revision: int = Field(ge=1, le=2147483647)
    cancellation_requested: Literal[True] = True
