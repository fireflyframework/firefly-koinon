# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded identity contracts for trusted publication and requested-source reads."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=64)]
Fingerprint = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class ProofValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReleaseProofPin(ProofValue):
    result_id: Identifier
    result_kind: Annotated[str, Field(min_length=1, max_length=32)]
    canonical_sha256: Fingerprint
    native_sha256: Fingerprint


class ReleaseProofSource(ProofValue):
    source_reference_id: Identifier
    kind: Literal["document", "dataset", "knowledge_version"]
    asset_id: Identifier
    source_id: Identifier | None = None
    source_version_id: Identifier | None = None
    extraction_id: Identifier | None = None
    source_part_id: Identifier | None = None
    source_part_sha256: Fingerprint | None = None
    used_revision: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    recorded_page: Annotated[int, Field(ge=1)] | None = None
    page_basis: Literal["recorded_loader"] | None = None
    knowledge_item_id: Identifier | None = None
    knowledge_version_id: Identifier | None = None
    knowledge_version: Annotated[int, Field(ge=1)] | None = None
    snapshot_id: Identifier | None = None
    supporting_result_ids: Annotated[tuple[Identifier, ...], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def coherent_identity(self):
        if tuple(sorted(set(self.supporting_result_ids))) != self.supporting_result_ids:
            raise ValueError("supporting results must be sorted unique identifiers")
        document = (self.source_version_id, self.extraction_id, self.source_part_id, self.source_part_sha256)
        if any(document) and (
            self.kind != "document"
            or not all(document)
            or self.page_basis != "recorded_loader"
            or self.used_revision != "source-part-sha256:" + str(self.source_part_sha256)
        ):
            raise ValueError("document identity must bind the complete exact recorded part")
        return self


class ReleaseProofHeader(ProofValue):
    release_result_id: Identifier
    projection_version: Literal[1] = 1
    tenant_id: Identifier
    thread_id: Identifier
    owner_subject: Annotated[str, Field(min_length=1, max_length=512)]
    run_id: Identifier
    message_id: Identifier
    user_message_id: Identifier
    generation_id: Identifier | None
    generation_start_sequence: Annotated[int, Field(ge=0)] | None
    generation_created_at: AwareDatetime | None
    reset_sequence: Annotated[int, Field(ge=0)]
    publication_sequence: Annotated[int, Field(ge=1)]
    policy_version: Literal["knowledge-only-v1", "knowledge-only-v2"]
    outcome: Literal["grounded", "refused", "review_required", "product_help"]
    canonical_seal_sha256: Fingerprint
    release_native_sha256: Fingerprint
    message_native_sha256: Fingerprint
    selection_native_sha256: Fingerprint
    active_selector_sha256: Fingerprint
    pin_count: Annotated[int, Field(ge=0, le=100)]
    source_count: Annotated[int, Field(ge=0, le=500)]
    provenance_complete: bool


class ReleaseProofCapture(ProofValue):
    header: ReleaseProofHeader
    pins: Annotated[tuple[ReleaseProofPin, ...], Field(max_length=100)]
    sources: Annotated[tuple[ReleaseProofSource, ...], Field(max_length=500)]
    state_sha256: Fingerprint


class ReleaseProofRequest(ProofValue):
    tenant_id: Identifier
    owner_subject: Annotated[str, Field(min_length=1, max_length=512)]
    thread_id: Identifier
    run_id: Identifier
    message_id: Identifier
    release_result_id: Identifier
    projection_version: Literal[1] = 1
    source_reference_id: Identifier | None = None


class ReleaseProofIdentity(ProofValue):
    header: ReleaseProofHeader
    state_sha256: Fingerprint
    source: ReleaseProofSource | None = None


class ReleaseProjectionClaim(ProofValue):
    job_id: Identifier
    projection_version: Literal[1] = 1
    claim_token: Identifier
    revision: Annotated[int, Field(ge=1)]
    claim_until: AwareDatetime
    tenant_id: Identifier | None = None
    state: Literal["ready", "running", "blocked", "complete"] = "running"


class ReleaseProjectionCursor(ProofValue):
    created_at: AwareDatetime
    release_result_id: Identifier
