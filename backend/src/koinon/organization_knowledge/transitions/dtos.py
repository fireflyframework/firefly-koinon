# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from koinon.organization_knowledge.dtos import OrganizationKnowledgeSettingsInput


class KnowledgeModeTransitionView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    tenant_id: str
    job_id: str
    revision: int = Field(ge=1)
    base_revision: int = Field(ge=0)
    base_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    active_mode: Literal["rag", "rlm"]
    requested_mode: Literal["rag", "rlm"]
    requested_settings: OrganizationKnowledgeSettingsInput
    status: Literal["queued", "running", "failed", "cancelled", "superseded", "succeeded"]
    stage: Literal["discovery", "preflight", "repair_views", "prepare_indexes", "verify", "activate"]
    counters: dict[str, int]
    stage_milliseconds: dict[str, int]
    pending_index_recoveries: int = Field(default=0, ge=0)
    progress_reason: Literal["knowledge_changed"] | None = None
    error_code: str | None
    error: str | None
    created_at: str
    updated_at: str


def transition_view(row, *, active_mode=None, pending_index_recoveries=0) -> KnowledgeModeTransitionView:
    return KnowledgeModeTransitionView(
        **{
            name: getattr(row, name)
            for name in KnowledgeModeTransitionView.model_fields
            if name
            not in {
                "requested_mode",
                "created_at",
                "updated_at",
                "active_mode",
                "pending_index_recoveries",
                "progress_reason",
            }
        },
        active_mode=active_mode or row.active_mode,
        pending_index_recoveries=pending_index_recoveries,
        progress_reason=row.cursor.get("progress_reason"),
        requested_mode=row.requested_settings["documents"]["answer_mode"],
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


class KnowledgeModeRevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_revision: int = Field(ge=1, strict=True)


class KnowledgeModeCurrentView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    transition: KnowledgeModeTransitionView | None


class KnowledgeModeIndexRecovery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    index_id: str
    job_id: str | None
    state: Literal["in_progress", "required", "resolved"]
    activation_job_id: str
    activation_lease_until: str | None
    index_status: str
    native_pointer_state: Literal["target", "previous", "other", "unavailable"] = "unavailable"
    expected_revision: int | None = Field(default=None, ge=1)
    expected_active_id: str | None = None
    expected_connection_revision: int | None = Field(default=None, ge=1)
    actions: list[Literal["finish", "restore_previous"]]
    message: str


class KnowledgeModeRecoveryReceipt(KnowledgeModeIndexRecovery):
    receipt_id: str
    attempt_revision: int = Field(ge=1)
    resolution_revision: int = Field(ge=1)
    resolution: Literal["pending", "finished", "restored", "aborted"]
    native_index_id: str
    provider_id: str
    model_id: str
    workspace_id: str
    native_workspace_id: str


class KnowledgeModeRecoveryPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    items: list[KnowledgeModeRecoveryReceipt]
    next_cursor: str | None


class KnowledgeModeTargetView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    kind: Literal["workspace", "document", "curated"]
    catalog_id: str
    workspace_id: str
    status: Literal["queued", "prepared", "ready", "waiting", "failed", "excluded"]
    error_code: str | None = None
    message: str | None = None
    action: (
        Literal[
            "reprocess_document",
            "inspect_document_job",
            "keep_rag",
            "inspect_source_integrity",
            "inspect_source_limits",
            "restart_preparation",
            "retry_preparation",
            "configure_models",
            "inspect_preparation",
            "inspect_index_job",
            "reconcile_index",
        ]
        | None
    ) = None
    index_id: str | None = None
    job_id: str | None = None
    job_status: str | None = None
    index_recovery: KnowledgeModeIndexRecovery | None = None
    lease_until: str | None = None
    source_version_id: str | None = None
    ingestion_extraction_id: str | None = None
    view_extraction_id: str | None = None
    raw_sha256: str | None = None
    raw_bytes: int | None = Field(default=None, ge=0)
    normalized_sha256: str | None = None
    parts: int | None = Field(default=None, ge=0)
    text_bytes: int | None = Field(default=None, ge=0)


class KnowledgeModeTargetPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    items: list[KnowledgeModeTargetView]
    next_cursor: str | None
