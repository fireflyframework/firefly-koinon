# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, SecretStr, model_validator

from koinon_sdk._base import InputModel, ResponseModel
from koinon_sdk.attachments import AttachmentCapabilities
from koinon_sdk.organization_knowledge import OrganizationKnowledgeSnapshot
from koinon_sdk.proposals import CatalogProposal, ProposalUpdate


class AuthorSummary(ResponseModel):
    subject: str
    display_name: str
    avatar_data_url: str | None = None
    avatar_version: str | None = None


class CatalogEntry(ResponseModel):
    created_by: str | None = None
    updated_by: str | None = None
    id: str
    tenant_id: str
    kind: str
    name: str
    parent_id: str | None = None
    workspace_id: str | None = None
    project_id: str | None = None
    description: str = ""
    status: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: str
    updated_at: str | None = None


class Membership(ResponseModel):
    managed: bool = False
    origin: Literal["manual", "corporate"] = "manual"
    source_id: str | None = None
    source_name: str | None = None
    expires_at: str | None = None
    id: str
    subject: str
    tenant_id: str
    workspace_id: str | None = None
    role: Literal["viewer", "analyst", "editor", "operator", "admin"]
    active: bool


class InvitationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["viewer", "analyst", "editor", "operator", "admin"]
    workspace_id: str | None = None
    expires_in_hours: int = Field(default=24, ge=1, le=168)
    label: str = Field(default="", max_length=120)


class Invitation(ResponseModel):
    id: str
    tenant_id: str
    workspace_id: str | None
    role: Literal["viewer", "analyst", "editor", "operator", "admin"]
    label: str
    created_by: str
    created_at: str
    expires_at: str
    status: Literal["pending", "accepted", "expired", "revoked"]
    accepted_at: str | None = None
    accepted_by: str | None = None


class InvitationCreated(ResponseModel):
    invitation: Invitation
    token: SecretStr


class InvitationToken(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr


class InvitationPreview(ResponseModel):
    id: str
    tenant_id: str
    tenant_name: str
    workspace_id: str | None
    workspace_name: str | None
    role: Literal["viewer", "analyst", "editor", "operator", "admin"]
    expires_at: str


class TenantContext(ResponseModel):
    id: str
    name: str
    roles: list[str] = Field(default_factory=list[str])
    permissions: list[str] = Field(default_factory=list[str])


class ContextResponse(ResponseModel):
    workspace_permissions: dict[str, list[str]] | None = None
    subject: str
    tenants: list[TenantContext] = Field(default_factory=list[TenantContext])
    memberships: list[Membership] = Field(default_factory=list[Membership])
    workspaces: list[CatalogEntry] = Field(default_factory=list[CatalogEntry])


class CatalogSummary(ResponseModel):
    child_count: int | None = None
    document_count: int | None = None
    dataset_count: int | None = None
    table_count: int | None = None
    row_count: int | None = None
    column_count: int | None = None
    page_count: int | None = None
    size_bytes: int | None = None
    format: str | None = None
    language: str | None = None
    tags: list[str] = Field(default_factory=list)


class Page[T](ResponseModel):
    summaries: dict[str, CatalogSummary] = Field(default_factory=dict)
    page: int | None = None
    size: int | None = None
    page_size: int | None = None
    pages: int | None = None
    next_cursor: str | None = None
    actors: dict[str, AuthorSummary] = Field(default_factory=dict)
    items: list[T]
    total: int | None = None


class ClarificationFrame(ResponseModel):
    questions: list[str]
    reasons: list[str] = Field(default_factory=list[str])


class AgentUsage(ResponseModel):
    agent: str
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0
    latency_ms: float = 0
    calls: int = 0


class UsageSummary(ResponseModel):
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0
    total_latency_ms: float = 0
    by_agent: list[AgentUsage] = Field(default_factory=list[AgentUsage])


class QueryResponse(ResponseModel):
    knowledge_settings_snapshot: OrganizationKnowledgeSnapshot | None = None
    query_id: str
    sql: str | None = None
    execution_status: Literal["OK", "REFINED_OK", "FAILED", "REJECTED_BY_FIREWALL"] | None
    preview: list[dict[str, JsonValue]] | None = None
    row_count: int | None = None
    elapsed_ms: int | None = None
    truncated: bool = False
    chart_hint: Literal["line", "bar", "table", "pie", "none"] | None = None
    explanation: str | None = None
    clarification: ClarificationFrame | None = None
    grounded_summary: dict[str, JsonValue] | None = None
    usage: UsageSummary | None = None
    snapshot_pins: dict[str, str] = Field(default_factory=dict)


class Citation(ResponseModel):
    document_id: str | None = None
    chunk_id: str | None = None
    section: str | None = None
    url: str | None = None
    id: str | None = None
    source_id: str | None = None
    asset_id: str | None = None
    title: str | None = None
    text: str | None = None
    page: int | None = None


class SearchHit(ResponseModel):
    id: str
    title: str
    text: str
    asset_id: str
    source_id: str | None = None
    score: float | None = None
    citations: list[Citation] = Field(default_factory=list[Citation])


class SearchResponse(ResponseModel):
    knowledge_settings_snapshot: OrganizationKnowledgeSnapshot | None = None
    hits: list[SearchHit]
    answer: str | None = None
    citations: list[Citation] = Field(default_factory=list[Citation])


class DocumentChunk(ResponseModel):
    id: str
    index: int
    total_chunks: int
    text: str
    char_start: int
    char_end: int
    page: int | None = None
    section_path: str | None = None
    embedding_model: str | None = None


class DocumentChunks(ResponseModel):
    document_id: str
    source_id: str
    native_source_id: str
    source_version_id: str | None = None
    extraction_id: str | None = None
    items: list[DocumentChunk]
    offset: int
    limit: int
    total: int
    next_offset: int | None = None


class Job(ResponseModel):
    id: str
    tenant_id: str
    resource_id: str
    kind: str
    status: str
    attempts: int
    max_attempts: int
    progress: int
    error: str | None = None
    result: dict[str, JsonValue] | None = None
    created_at: str
    updated_at: str


class ProviderCapability(ResponseModel):
    id: str
    name: str
    kind: str
    configured: bool
    available: bool
    reason: str | None = None
    capabilities: list[str] = Field(default_factory=list[str])


class FeatureCapability(ResponseModel):
    id: str
    name: str
    available: bool
    reason: str | None = None


class CatalogCapability(ResponseModel):
    ready: bool


class AgenticCapability(ResponseModel):
    configured: bool
    verified: bool


class DomainCapability(ResponseModel):
    installed: bool
    registered: bool
    beans: int | None = None
    qualified: bool | None = None
    reason: str | None = None


class Capabilities(ResponseModel):
    attachments: AttachmentCapabilities | None = None
    catalog: CatalogCapability | None = None
    agentic: AgenticCapability | None = None
    domains: dict[str, DomainCapability] = Field(default_factory=dict)
    providers: list[ProviderCapability]
    features: list[FeatureCapability]


class Column(ResponseModel):
    id: str
    name: str
    data_type: str
    description: str | None = None
    pii_tag: str | None = None


class SchemaTable(ResponseModel):
    sheet_or_json_path: str | None = None
    id: str
    name: str
    snapshot_id: str | None = None
    columns: list[Column]


class DatasetSchema(ResponseModel):
    tables: list[SchemaTable]


class LineageNode(ResponseModel):
    id: str
    label: str
    kind: str


class LineageEdge(ResponseModel):
    source: str
    target: str
    label: str | None = None


class Lineage(ResponseModel):
    nodes: list[LineageNode]
    edges: list[LineageEdge]


class AuditEvent(ResponseModel):
    id: str
    subject: str
    action: str
    resource_id: str | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: str


class UploadResponse(ResponseModel):
    source: CatalogEntry
    assets: list[CatalogEntry]
    job_id: str | None = None


class KnowledgeScope(ResponseModel):
    workspace_id: str | None = None
    project_id: str | None = None
    collection_id: str | None = None
    asset_ids: list[str] | None = None


class SetupCheck(ResponseModel):
    model_id: str | None = None
    capability: Literal["chat", "streaming", "tools", "image_input", "audio_input"] | None = None
    supported: bool | None = None
    verified: bool | None = None
    options_key: str | None = None
    observed_at: str | None = None
    id: str
    status: Literal["passed", "failed", "needs_setup", "unverified"]
    message: str


class ModelParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    max_tokens: int = Field(default=4096, ge=64, le=16384, strict=True)
    temperature: float | None = Field(default=None, ge=0, le=2, strict=True)
    top_p: float | None = Field(default=None, ge=0, le=1, strict=True)
    top_k: int | None = Field(default=None, ge=1, le=1000, strict=True)
    seed: int | None = Field(default=None, ge=-(2**31), le=2**31 - 1, strict=True)
    stop_sequences: tuple[Annotated[str, Field(min_length=1, max_length=256)], ...] | None = Field(
        default=None, max_length=8
    )
    request_timeout: float | None = Field(default=None, ge=0.1, le=120, strict=True)
    reasoning: Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None = None
    reasoning_budget_tokens: int | None = Field(default=None, ge=1024, le=16000, strict=True)
    parallel_tool_calls: bool | None = Field(default=None, strict=True)
    store_responses: bool | None = Field(default=None, strict=True)
    output_verbosity: Literal["low", "medium", "high"] | None = None

    @model_validator(mode="after")
    def _one_reasoning_control(self):
        if self.reasoning is not None and self.reasoning_budget_tokens is not None:
            raise ValueError("Choose reasoning or reasoning_budget_tokens, not both")
        return self


class CapabilityState(ResponseModel):
    supported: bool | None = None
    verified: bool = False


class ModelCapability(ResponseModel):
    image_input: CapabilityState = Field(default_factory=CapabilityState)
    audio_input: CapabilityState = Field(default_factory=CapabilityState)
    option_fields: list[str] = Field(default_factory=list[str])
    model_id: str
    chat: CapabilityState
    streaming: CapabilityState
    tools: CapabilityState
    observed_tools: list[str] = Field(default_factory=list[str])


class ModelConnection(ResponseModel):
    id: str
    ownership: Literal["deployment"]
    read_only: Literal[True]
    provider: str | None = None
    model_id: str | None = None
    configured: bool
    available: bool | None
    status: Literal["passed", "failed", "needs_setup", "unverified"]
    reason: str


class ProviderSupport(ResponseModel):
    id: str
    native_supported: bool
    exposed: bool
    kind: str | None = None
    api: str | None = None
    model_class: str
    reason: str | None = None


class NativeAdapter(ResponseModel):
    ownership: Literal["deployment"]
    read_only: Literal[True]
    model_class: str
    provider_identity: str
    profile_status: Literal["unverified"]
    reason: str


class ModelProvider(ResponseModel):
    native_adapter: NativeAdapter | None = None
    api: Literal["chat", "responses", "messages"] | None = None
    model_class: Literal["OpenAIChatModel", "OpenAIResponsesModel", "AnthropicModel"] | None = None
    configured: bool = False
    connected: bool = False
    discovered: bool = False
    model_capabilities: list[ModelCapability] = Field(default_factory=list[ModelCapability])
    configuration_ownership: Literal["tenant"] = "tenant"
    credential_ownership: Literal["tenant", "none"] = "none"
    ambient_credentials: Literal[False] = False
    id: str
    name: str
    kind: Literal["ollama", "openai", "anthropic"]
    base_url: str
    model_ids: list[str]
    enabled: bool
    revision: int
    secret_configured: bool
    validated: bool
    checks: list[SetupCheck]


class FieldOption(ResponseModel):
    value: str
    label: str


class FieldSchema(ResponseModel):
    options: list[FieldOption] = Field(default_factory=list[FieldOption])
    name: str
    label: str
    type: Literal["text", "url", "secret", "string_list", "select"]
    required: bool
    write_only: bool | None = None
    default: str | None = None


class ProviderType(ResponseModel):
    id: str
    name: str
    fields: list[FieldSchema]


class OperationalObservation(ResponseModel):
    configured: bool
    available: bool | None
    status: Literal["passed", "failed", "unknown"]
    observed_at: str
    reason: str


class ConnectionPool(ResponseModel):
    size: int | None = None
    max_overflow: int | None = None
    timeout: float | None = None
    recycle: int
    pre_ping: bool


class PoolUsage(ResponseModel):
    size: int | None = None
    checked_out: int | None = None
    overflow: int | None = None


class RoleObservation(OperationalObservation):
    superuser: bool | None = None
    bypass_rls: bool | None = None


class DeploymentDatasource(OperationalObservation):
    id: str
    kind: Literal["database"]
    driver: str
    pool: ConnectionPool
    pool_usage: PoolUsage
    role_policy: RoleObservation


class DeploymentStorage(OperationalObservation):
    ownership: Literal["deployment"] | None = None
    read_only: Literal[True] | None = None
    id: Literal["documents", "structured"]
    backend: str | None = None
    store_originals: bool | None = None


class DeploymentIndex(OperationalObservation):
    id: str
    workspace_id: str | None = None
    vector_extension: bool | None = None
    embedding_sets: int | None = None
    physical_indexes: int | None = None


class OperationalLimits(ResponseModel):
    worker_concurrency: int
    max_queued_per_subject: int
    job_lease_seconds: int
    max_index_workspaces: int


class MetricsObservation(OperationalObservation):
    exporter_configured: bool | None = None
    names: list[str] = Field(default_factory=list[str])


class DeploymentConfiguration(ResponseModel):
    ownership: Literal["deployment"]
    read_only: Literal[True]
    datasources: list[DeploymentDatasource]
    storage: list[DeploymentStorage]
    indexes: list[DeploymentIndex]
    metrics: MetricsObservation
    limits: OperationalLimits


class Configuration(ResponseModel):
    framework_providers: list[ProviderSupport] = Field(default_factory=list[ProviderSupport])
    model_options_schema: dict[str, JsonValue] = Field(default_factory=dict)
    deployment: DeploymentConfiguration | None = None
    providers: list[ModelProvider]
    provider_types: list[ProviderType]
    connections: list[ModelConnection]
    checks: list[SetupCheck]


AgentTool = Literal["search_knowledge", "inspect_schema", "query_dataset", "propose_catalog_update"]
MessageStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class AgentConfiguration(ResponseModel):
    model_settings: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue])
    input_modalities: list[Literal["text", "image", "audio"]] = Field(default_factory=lambda: ["text"])
    input_modality_policy: str | None = None
    model_options_supported: list[str] = Field(default_factory=list[str])
    api: Literal["chat", "responses", "messages"] | None = None
    model_class: Literal["OpenAIChatModel", "OpenAIResponsesModel", "AnthropicModel"] | None = None
    model_options: ModelParameters = Field(default_factory=ModelParameters)
    configured: bool = False
    can_run: bool = False
    dependencies: list[ModelConnection] = Field(default_factory=list[ModelConnection])
    id: str
    name: str
    description: str
    provider_id: str
    model_id: str
    tools: list[AgentTool]
    scope: KnowledgeScope
    instructions: str
    enabled: bool
    revision: int
    status: Literal["ready", "needs_setup", "unverified", "disabled"]
    checks: list[SetupCheck]


class ValidationResult(ResponseModel):
    connected: bool = False
    discovered: bool = False
    provider_id: str
    revision: int
    status: Literal["ready", "needs_setup", "unverified"]
    checks: list[SetupCheck]


class ChatThread(ResponseModel):
    revision: int
    title_source: Literal["default", "manual", "ai"]
    folder_id: str | None
    archived_at: str | None
    id: str
    title: str
    scope: KnowledgeScope
    created_at: str
    updated_at: str


class ChatFolder(ResponseModel):
    id: str
    name: str
    parent_id: str | None
    scope: KnowledgeScope
    revision: int
    conversation_count: int
    created_at: str
    updated_at: str


class OpenUIArtifact(ResponseModel):
    id: str
    kind: Literal["openui"]
    language: str
    complete: bool
    run_id: str


class Presentation(ResponseModel):
    locale: str | None = None
    time_zone: str | None = None
    response_language: str | None = None


class AnswerPolicy(ResponseModel):
    outcome: Literal["grounded", "refused", "review_required"]
    code: str | None = None
    reason: str | None = None


class AttachmentHistorySummary(ResponseModel):
    id: str
    filename: str
    media_type: str
    kind: Literal["document", "image", "bundle"]
    size_bytes: int
    sha256: str
    status: Literal["storing", "queued", "extracting", "ready", "failed", "cancelled", "expired", "deleted"]
    revision: int
    expires_at: str
    available: bool


class ToolActivity(ResponseModel):
    call_id: str
    tool_name: Literal[
        "search_knowledge",
        "inspect_schema",
        "query_dataset",
        "search_private_attachments",
        "propose_catalog_update",
    ]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    occurred_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    summary: str
    result_id: str | None = None


class ChatMessage(ResponseModel):
    tool_activities: list[ToolActivity] | None = None
    tool_activity_count: int | None = None
    tool_activity_has_more: bool | None = None
    attachments: list[AttachmentHistorySummary] = Field(default_factory=list[AttachmentHistorySummary])

    answer_policy: AnswerPolicy | None = None
    presentation: Presentation = Field(default_factory=Presentation)
    event_cursor: str | None = None
    id: str
    run_id: str | None = None
    role: Literal["user", "assistant"]
    text: str
    status: MessageStatus
    citations: list[Citation]
    artifacts: list[OpenUIArtifact]
    created_at: str


class ChatRun(ResponseModel):
    event_cursor: str | None = None
    run_id: str
    message_id: str
    status: MessageStatus | None = None


class AttachmentEvidenceItem(ResponseModel):
    id: str
    filename: str
    media_type: str
    sha256: str
    revision: int
    complete: bool
    chunk_ids: list[str]
    total_chunks: int
    warnings: list[str]


class AttachmentEvidence(ResponseModel):
    attachments: list[AttachmentEvidenceItem]


class ChatEventData(ResponseModel):
    proposal_update: ProposalUpdate | None = None
    tool_activity: ToolActivity | None = None
    answer_policy: AnswerPolicy | None = None
    presentation: Presentation | None = None
    text: str | None = None
    stage: str | None = None
    message: str | None = None
    status: MessageStatus | None = None
    code: str | None = None
    message_id: str | None = None
    artifact: OpenUIArtifact | None = None
    citation: Citation | None = None


class StreamEvent(ResponseModel):
    id: str
    type: str
    data: ChatEventData


class EvidenceResult(ResponseModel):
    id: str
    run_id: str
    kind: Literal["search", "query", "schema", "lineage", "attachment", "proposal"]
    data: SearchResponse | QueryResponse | DatasetSchema | Lineage | AttachmentEvidence | CatalogProposal


class ProviderInput(InputModel):
    api: Literal["chat", "responses", "messages"] | None = None
    name: str | None = None
    kind: Literal["ollama", "openai", "anthropic"] | None = None
    base_url: str | None = None
    model_ids: list[str] | None = None
    secret: SecretStr | None = None
    enabled: bool | None = None


class AgentInput(InputModel):
    model_options: ModelParameters | None = None
    name: str | None = None
    description: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    tools: list[AgentTool] | None = None
    scope: KnowledgeScope | None = None
    instructions: str | None = None
    enabled: bool | None = None


class RunInput(InputModel):
    attachment_ids: list[str] = Field(default_factory=list, max_length=10)
    agent_id: str
    message: str
    scope: KnowledgeScope | None = None
    client_request_id: str


class UserProfile(ResponseModel):
    subject: str
    display_name: str
    locale: str
    time_zone: str
    response_language: str
    avatar_url: str | None = None
    avatar_version: str | None = None


class ProfileUpdate(InputModel):
    display_name: str | None = None
    locale: str | None = None
    time_zone: str | None = None
    response_language: str | None = None


class Person(ResponseModel):
    profile_id: str | None = None
    subject: str
    display_name: str
    avatar_url: str | None = None
    avatar_version: str | None = None


class PersonalToken(ResponseModel):
    id: str
    name: str
    tenant_id: str
    prefix: str
    scopes: list[str]
    workspace_ids: list[str] | None = None
    asset_ids: list[str] | None = None
    expires_at: str
    revoked_at: str | None = None
    last_used_at: str | None = None
    created_at: str


class TokenCreated(PersonalToken):
    token: SecretStr


class TokenInput(InputModel):
    name: str
    tenant_id: str
    scopes: list[str]
    expires_at: AwareDatetime
    workspace_ids: list[str] | None = None
    asset_ids: list[str] | None = None


class TokenScope(ResponseModel):
    id: str
    name: str
    dependencies: list[str]


class TokenScopeOptions(ResponseModel):
    items: list[TokenScope]
    max_lifetime_days: int
    max_active_per_user: int
