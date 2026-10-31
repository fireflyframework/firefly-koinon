# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from koinon.evidence.dtos import SourceReference

Identifier = Annotated[str, Field(min_length=1, max_length=64)]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Action = Literal["create_draft", "create_published", "update_draft", "update_published", "publish_draft"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KnowledgeContent(Frozen):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=262144)
    summary: str | None = Field(default=None, max_length=4000)
    domain: Literal[
        "legal",
        "compliance",
        "process",
        "network",
        "ai_platform",
        "executive",
        "hr",
        "cto",
        "engineering",
        "security",
        "other",
    ] = "other"
    tags: tuple[Annotated[str, Field(min_length=1, max_length=128)], ...] = Field(default=(), max_length=64)

    @field_validator("body")
    @classmethod
    def bounded_bytes(cls, value: str) -> str:
        if len(value.encode()) > 262144 or not value.strip():
            raise ValueError("Knowledge body must contain text within256KiB")
        return value


class UserStatementOrigin(Frozen):
    kind: Literal["user_statement"]


class ExternalProposalOrigin(Frozen):
    kind: Literal["external_proposal"]
    source_receipt_ids: tuple[Identifier, ...] = Field(default=(), max_length=32)

    @field_validator("source_receipt_ids")
    @classmethod
    def distinct(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Select distinct source read receipts")
        return value


class ConversationOrigin(Frozen):
    kind: Literal["conversation"]
    thread_id: Identifier
    message_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=200)

    @field_validator("message_ids")
    @classmethod
    def distinct(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Select distinct messages")
        return value


class KnowledgeIntentInput(Frozen):
    action: Action
    destination_id: Identifier
    target_item_id: Identifier | None = None
    expected_version: int | None = Field(default=None, ge=1)
    content: KnowledgeContent
    origin: Annotated[
        UserStatementOrigin | ConversationOrigin | ExternalProposalOrigin, Field(discriminator="kind")
    ]

    @model_validator(mode="after")
    def exact_target(self):
        creating = self.action in {"create_draft", "create_published"}
        if creating and (self.target_item_id is not None or self.expected_version is not None):
            raise ValueError("Creation does not accept an existing target version")
        if not creating and (self.target_item_id is None or self.expected_version is None):
            raise ValueError("Changes require an exact target item and expected version")
        return self


class UserStatementEvidence(Frozen):
    kind: Literal["user_statement"] = "user_statement"
    text: str = Field(min_length=1, max_length=262144)
    sha256: Sha256
    author_subject: str = Field(min_length=1, max_length=512)
    recorded_at: AwareDatetime
    authority: Literal["user_authored"] = "user_authored"


class ExternalProposalEvidence(Frozen):
    kind: Literal["external_proposal"] = "external_proposal"
    text: str = Field(min_length=1, max_length=262144)
    sha256: Sha256
    submitted_by: str = Field(min_length=1, max_length=512)
    credential_id: Identifier
    application_id: Identifier | None = None
    source_receipt_ids: tuple[Identifier, ...] = Field(default=(), max_length=32)
    recorded_at: AwareDatetime
    authority: Literal["unverified"] = "unverified"
    provider: None = None
    model: None = None


class DocumentEvidence(Frozen):
    kind: Literal["document_passage"] = "document_passage"
    source: SourceReference

    @model_validator(mode="after")
    def exact_document(self):
        if (
            self.source.kind != "document"
            or not (self.source.chunk_id or self.source.source_part_id)
            or not self.source.used_revision
        ):
            raise ValueError("A document passage requires an exact captured chunk or immutable part")
        return self


class StructuredEvidence(Frozen):
    kind: Literal["structured_snapshot"] = "structured_snapshot"
    source: SourceReference

    @model_validator(mode="after")
    def exact_snapshot(self):
        if (
            self.source.kind != "dataset"
            or not self.source.snapshot_id
            or not self.source.used_revision
            or not self.source.query_id
        ):
            raise ValueError("Structured factual evidence requires an executed query and exact snapshot")
        return self


KnowledgeEvidence = Annotated[
    UserStatementEvidence | DocumentEvidence | StructuredEvidence | ExternalProposalEvidence,
    Field(discriminator="kind"),
]


class KnowledgeDestination(Frozen):
    id: Identifier
    workspace_id: Identifier
    project_id: Identifier
    name: str = Field(min_length=1, max_length=255)
    ancestry_digest: Sha256


class KnowledgeCommitReceipt(Frozen):
    operation_id: Identifier
    intent_id: Identifier
    intent_revision: int = Field(ge=1)
    authorization_digest: Sha256
    item_id: Identifier
    native_item_id: Identifier
    native_version_id: Identifier
    version: int = Field(ge=1)
    serving_version: int | None = Field(default=None, ge=1)
    action: Action
    content_sha256: Sha256
    evidence_sha256: Sha256
    committed_at: AwareDatetime
    retrieval_state: Literal["not_published", "lexical_ready", "indexing", "ready", "unavailable"]
    reason: str | None = Field(default=None, max_length=512)


class KnowledgeIntent(Frozen):
    id: Identifier
    revision: int = Field(ge=1)
    tenant_id: Identifier
    owner_subject: str = Field(min_length=1, max_length=512)
    action: Action
    destination: KnowledgeDestination
    target_item_id: Identifier
    expected_version: int | None = Field(default=None, ge=1)
    before: KnowledgeContent | None = None
    after: KnowledgeContent
    evidence: tuple[KnowledgeEvidence, ...] = Field(min_length=1, max_length=500)
    authorization_digest: Sha256
    status: Literal["preview", "committing", "committed", "cancelled", "stale", "unresolved"]
    created_at: AwareDatetime
    expires_at: AwareDatetime
    receipt: KnowledgeCommitReceipt | None = None


class KnowledgeConfirmation(Frozen):
    confirm: Literal[True]
    expected_revision: int = Field(ge=1)
    authorization_digest: Sha256

    @field_validator("confirm", mode="before")
    @classmethod
    def explicit(cls, value):
        if value is not True:
            raise ValueError("Explicit confirmation is required")
        return value


class CommittedKnowledge(Frozen):
    status: Literal["committed"] = "committed"
    receipt: KnowledgeCommitReceipt


class PendingKnowledgeCommit(Frozen):
    status: Literal["pending"] = "pending"
    operation_id: Identifier
    intent_id: Identifier
    reason: Literal["commit_outcome_unresolved"] = "commit_outcome_unresolved"


KnowledgeCommitOutcome = Annotated[CommittedKnowledge | PendingKnowledgeCommit, Field(discriminator="status")]


class KnowledgeCancellation(Frozen):
    expected_revision: int = Field(ge=1)


class KnowledgeVersionView(Frozen):
    item_id: Identifier
    version: int = Field(ge=1)
    version_id: Identifier
    publication: Literal["draft", "published"]
    serving: bool
    content: KnowledgeContent
    evidence: tuple[KnowledgeEvidence, ...] = Field(min_length=1, max_length=500)
    content_sha256: Sha256
    evidence_sha256: Sha256
    operation_id: Identifier
    author_subject: str = Field(min_length=1, max_length=512)
    committed_at: AwareDatetime


class KnowledgeItemView(Frozen):
    id: Identifier
    tenant_id: Identifier
    workspace_id: Identifier
    project_id: Identifier
    destination_id: Identifier
    head_version: int = Field(ge=1)
    serving_version: int | None = Field(default=None, ge=1)
    selected_version: KnowledgeVersionView


class KnowledgeItemSummary(Frozen):
    id: Identifier
    tenant_id: Identifier
    workspace_id: Identifier
    project_id: Identifier
    destination_id: Identifier
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(max_length=4000)
    head_version: int = Field(ge=1)
    serving_version: int | None = Field(default=None, ge=1)


class KnowledgeItemPage(Frozen):
    items: tuple[KnowledgeItemSummary, ...] = Field(max_length=100)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool
