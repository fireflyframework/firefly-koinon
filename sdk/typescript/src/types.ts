// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {AttachmentCapabilities,AttachmentHistorySummary,CatalogProposal,ProposalUpdate} from './generated.js';
export type Json = null | boolean | number | string | Json[] | {[key:string]:Json};
export type ResourceKind = 'workspace'|'project'|'collection'|'corpus'|'source'|'document'|'dataset'|'chunk'|'table'|'index_version'|'query_session';
export interface CatalogEntry {
 created_by?:string; updated_by?:string; id:string; tenant_id:string; kind:ResourceKind; name:string; description:string; status:string;
 parent_id:string|null; workspace_id:string|null; project_id:string|null; metadata:Record<string,Json>;
 created_at:string; updated_at?:string;
}
export interface EntryCreate {kind:ResourceKind;name:string;description?:string;parent_id?:string|null;metadata?:Record<string,Json>}
export interface EntryUpdate {name?:string;description?:string;metadata?:Record<string,Json>}
export interface CatalogFilter {page?:number;page_size?:number;q?:string;status?:string;sort?:'name'|'kind'|'created_at'|'updated_at';format?:string;tag?:string;order?:'asc'|'desc';view?:'raw'|'library';include_archived?:boolean;kind?:ResourceKind;parent_id?:string;project_id?:string;workspace_id?:string;[key:string]:string|number|boolean|undefined}
export interface Membership {managed?:boolean;origin?:'manual'|'corporate';source_id?:string|null;source_name?:string|null;expires_at?:string|null;id:string;subject:string;tenant_id:string;workspace_id:string|null;role:'viewer'|'analyst'|'editor'|'operator'|'admin';active:boolean}
export interface AuditFilter {q?:string;action?:string;subject?:string;from_date?:string;through_date?:string;time_zone?:string;page?:number;page_size?:number;sort?:'created_at'|'action';order?:'asc'|'desc';[key:string]:string|number|undefined}
export interface MembershipFilter {q?:string;role?:Membership['role'];scope?:'all'|'tenant'|'workspace';workspace_id?:string;page?:number;page_size?:number;[key:string]:string|number|undefined}
export interface InvitationFilter {workspace_id?:string;status?:'pending'|'accepted'|'revoked'|'expired';page?:number;page_size?:number;[key:string]:string|number|undefined}
export interface InvitationInput {role:Membership['role'];workspace_id?:string|null;expires_in_hours?:number;label?:string}
export interface Invitation {id:string;tenant_id:string;workspace_id:string|null;role:Membership['role'];label:string;created_by:string;created_at:string;expires_at:string;status:'pending'|'accepted'|'revoked'|'expired';accepted_at?:string|null;accepted_by?:string|null}
export interface InvitationCreated {invitation:Invitation;token:string}
export interface InvitationPreview {id:string;tenant_id:string;tenant_name:string;workspace_id:string|null;workspace_name:string|null;role:Membership['role'];expires_at:string}
export interface TenantContext {id:string;name:string;roles:string[];permissions:string[]}
export interface ContextResponse {workspace_permissions?:Record<string,string[]>;subject:string;tenants:TenantContext[];memberships:Membership[];workspaces:CatalogEntry[]}
export interface ProviderCapability {id:string;name:string;kind:string;configured:boolean;available:boolean;reason?:string|null;capabilities:string[]}
export interface Capabilities {attachments?:AttachmentCapabilities;catalog?:{ready:boolean};agentic?:{configured:boolean;verified:boolean};domains?:Record<string,DomainCapability>;providers:ProviderCapability[];features:{id:string;name:string;available:boolean;reason?:string|null}[]}
export interface Citation {id?:string;source_id?:string;asset_id?:string;document_id?:string;chunk_id?:string;title?:string;text?:string;page?:number|null;section?:string|null;url?:string|null}
export interface SearchRequest {question:string;workspace_id?:string;project_id?:string;collection_id?:string;asset_ids?:string[];limit?:number;answer?:boolean}
export interface SearchHit {id:string;title:string;text:string;score?:number|null;asset_id:string;source_id?:string;citations?:Citation[]}
export interface SearchResponse {hits:SearchHit[];answer?:string;citations?:Citation[]}
export interface QueryRequest {dataset_id:string;question?:string;conversation_id?:string|null;sql?:string|null}
export interface QueryResponse {query_id:string;sql?:string|null;execution_status:'OK'|'REFINED_OK'|'FAILED'|'REJECTED_BY_FIREWALL'|null;preview?:Record<string,Json>[]|null;row_count?:number|null;truncated?:boolean;elapsed_ms?:number|null;chart_hint?:'line'|'bar'|'table'|'pie'|'none'|null;explanation?:string|null;clarification?:ClarificationFrame|null;grounded_summary?:Record<string,Json>|null;usage?:UsageSummary|null;snapshot_pins?:Record<string,string>;citations?:Citation[]}
export interface Column {id:string;name:string;data_type:string;description?:string|null;pii_tag?:string|null}
export interface SchemaTable {sheet_or_json_path?:string|null;id:string;name:string;snapshot_id?:string|null;columns:Column[]}
export interface DatasetSchema {tables:SchemaTable[]}
export interface Job {id:string;tenant_id:string;resource_id:string;kind:string;status:string;attempts:number;max_attempts:number;progress:number;error:string|null;created_at:string;updated_at:string;result:Record<string,Json>|null}
export interface UploadResponse {source:CatalogEntry;assets:CatalogEntry[];job_id?:string}
export interface LineageNode {id:string;label:string;kind:string;[key:string]:Json|undefined}
export interface LineageEdge {source:string;target:string;label?:string}
export interface Lineage {nodes:LineageNode[];edges:LineageEdge[]}
export interface AuditEvent {id:string;subject:string;action:string;resource_id:string|null;details:Record<string,Json>;created_at:string}
export interface CatalogSummary {child_count:number|null;document_count:number|null;dataset_count:number|null;table_count:number|null;row_count:number|null;column_count:number|null;page_count:number|null;size_bytes:number|null;format:string|null;language:string|null;tags:string[]}
export interface Page<T> {summaries?:Record<string,CatalogSummary>;next_cursor?:string|null;actors?:Record<string,PublicActor>;items:T[];total?:number;page?:number;size?:number;page_size?:number;pages?:number}
export interface MemberInput {subject:string;role:Membership['role'];workspace_id?:string|null}
export interface KnowledgeScope {workspace_id?:string;project_id?:string;collection_id?:string;asset_ids?:string[]}
export interface SetupCheck {id:string;status:'passed'|'failed'|'needs_setup'|'unverified';message:string;model_id?:string;capability?:'chat'|'streaming'|'tools'|'image_input'|'audio_input';supported?:boolean|null;verified?:boolean}
export type ModelApi='chat'|'responses'|'messages';
export type NativeModelClass='OpenAIChatModel'|'OpenAIResponsesModel'|'AnthropicModel';
export interface ModelParameters {max_tokens?:number;temperature?:number;top_p?:number;top_k?:number;seed?:number;stop_sequences?:string[];request_timeout?:number;reasoning?:'none'|'minimal'|'low'|'medium'|'high'|'xhigh';reasoning_budget_tokens?:number;parallel_tool_calls?:boolean;store_responses?:boolean;output_verbosity?:'low'|'medium'|'high'}
export interface CapabilityState {supported:boolean|null;verified:boolean}
export interface ModelCapability {model_id:string;chat:CapabilityState;streaming:CapabilityState;tools:CapabilityState;image_input?:CapabilityState;audio_input?:CapabilityState;observed_tools:string[];option_fields?:string[]}
export interface ModelConnection {id:string;ownership:'deployment';read_only:true;provider?:string|null;model_id?:string|null;configured:boolean;available:boolean|null;status:'passed'|'failed'|'needs_setup'|'unverified';reason:string;tool?:AgentTool}
export interface ProviderSupport {id:string;native_supported:boolean;exposed:boolean;kind?:string|null;api?:ModelApi|null;model_class:string;reason?:string|null}
export interface NativeAdapter {ownership:'deployment';read_only:true;model_class:string;provider_identity:string;profile_status:'unverified';reason:string}
export interface ModelProvider {native_adapter?:NativeAdapter;api?:ModelApi;model_class?:NativeModelClass;configured?:boolean;connected?:boolean;discovered?:boolean;model_capabilities?:ModelCapability[];configuration_ownership?:'tenant';credential_ownership?:'tenant'|'none';ambient_credentials?:false;id:string;name:string;kind:'ollama'|'openai'|'anthropic';base_url:string;model_ids:string[];enabled:boolean;revision:number;secret_configured:boolean;validated:boolean;checks:SetupCheck[]}
export interface ProviderInput {api?:ModelApi;name?:string;kind?:ModelProvider['kind'];base_url?:string;model_ids?:string[];secret?:string|null;enabled?:boolean}
export interface AgentConfiguration {model_settings?:Record<string,Json>;input_modalities?:Array<'text'|'image'|'audio'>;input_modality_policy?:string;api?:ModelApi;model_class?:NativeModelClass;model_options?:ModelParameters;model_options_supported?:string[];configured?:boolean;can_run?:boolean;dependencies?:ModelConnection[];id:string;name:string;description:string;provider_id:string;model_id:string;tools:AgentTool[];scope:KnowledgeScope;instructions:string;enabled:boolean;revision:number;status:'ready'|'needs_setup'|'unverified'|'disabled';checks:SetupCheck[]}
export type AgentTool='search_knowledge'|'inspect_schema'|'query_dataset'|'propose_catalog_update';
export interface AgentInput {model_options?:ModelParameters;name?:string;description?:string;provider_id?:string;model_id?:string;tools?:AgentTool[];scope?:KnowledgeScope;instructions?:string;enabled?:boolean}
export interface FieldSchema {name:string;label:string;type:'text'|'url'|'secret'|'string_list'|'select';options?:{value:string;label:string}[];required:boolean;write_only?:boolean;default?:string}
export interface ResourceObservation {configured:boolean;available:boolean|null;status:'passed'|'failed'|'unknown';observed_at:string;reason:string}
export interface DatasourceObservation extends ResourceObservation {id:string;kind:'database';driver:string;pool:{size:number|null;max_overflow:number|null;timeout:number|null;recycle:number;pre_ping:boolean};pool_usage?:{size:number;checked_out:number;overflow:number};role_policy?:ResourceObservation&{superuser?:boolean;bypass_rls?:boolean}}
export interface StorageObservation extends ResourceObservation {id:string;backend?:string|null;ownership?:'deployment';read_only?:true;store_originals?:boolean}
export interface IndexObservation extends ResourceObservation {id:string;workspace_id?:string;vector_extension?:boolean;embedding_sets?:number;physical_indexes?:number}
export interface MetricsObservation extends ResourceObservation {exporter_configured:boolean;names:string[]}
export interface DeploymentConfiguration {ownership:'deployment';read_only:true;datasources:DatasourceObservation[];storage:StorageObservation[];indexes:IndexObservation[];metrics:MetricsObservation;limits:{worker_concurrency:number;max_queued_per_subject:number;job_lease_seconds:number;max_index_workspaces:number}}
export interface Configuration {model_options_schema?:Record<string,Json>;framework_providers?:ProviderSupport[];deployment?:DeploymentConfiguration;providers:ModelProvider[];provider_types:{id:string;name:string;fields:FieldSchema[]}[];connections:ModelConnection[];checks:SetupCheck[]}
export interface ValidationResult {connected?:boolean;discovered?:boolean;provider_id:string;revision:number;status:'ready'|'needs_setup'|'unverified';checks:SetupCheck[]}
export interface ChatThread {id:string;title:string;title_source:'default'|'manual'|'ai';revision:number;folder_id:string|null;archived_at:string|null;scope:KnowledgeScope;created_at:string;updated_at:string}
export interface ChatFolder {id:string;name:string;parent_id:string|null;scope:KnowledgeScope;revision:number;conversation_count:number;created_at:string;updated_at:string}
export interface ThreadCreate {title?:string;folder_id?:string|null;scope?:KnowledgeScope}
export interface FolderCreate {name:string;parent_id?:string|null;scope?:KnowledgeScope}
export interface FolderPatch {expected_revision:number;name?:string;parent_id?:string|null}
export interface ThreadPatch {expected_revision:number;title?:string;folder_id?:string|null;archived?:boolean}
export interface TitleRequest {agent_id:string;expected_revision:number}
export interface TitleSuggestion {title:string;based_on_revision:number}
export interface FolderFilter {root_only?:boolean;q?:string;page?:number;page_size?:number;parent_id?:string;workspace_id?:string;sort?:'name'|'created_at'|'updated_at';order?:'asc'|'desc';[key:string]:string|number|boolean|undefined}
export interface ThreadFilter {q?:string;page?:number;page_size?:number;folder_id?:string;unfiled?:boolean;project_id?:string;workspace_id?:string;status?:'active'|'archived'|'all';sort?:'title'|'created_at'|'updated_at';order?:'asc'|'desc';[key:string]:string|number|boolean|undefined}
export type MessageStatus='queued'|'running'|'completed'|'failed'|'cancelled';
export interface OpenUIArtifact {id:string;kind:'openui';language:string;complete:boolean;run_id:string}
export interface AnswerPolicy {outcome:'grounded'|'refused'|'review_required';code?:string|null;reason?:string|null}
export interface ChatMessage {tool_activities?:ToolActivity[];tool_activity_count?:number;tool_activity_has_more?:boolean;attachments?:AttachmentHistorySummary[];answer_policy?:AnswerPolicy;presentation?:Presentation;id:string;run_id?:string;event_cursor?:string;role:'user'|'assistant';text:string;status:MessageStatus;citations:Citation[];artifacts:OpenUIArtifact[];created_at:string}
export interface RunInput {attachment_ids?:string[];agent_id:string;message:string;scope?:KnowledgeScope;client_request_id:string}
export interface ChatRun {event_cursor?:string;run_id:string;message_id:string;status?:MessageStatus}
export type ChatEventData = {proposal_update?:ProposalUpdate;tool_activity?:ToolActivity;answer_policy?:AnswerPolicy;presentation?:Presentation;text?:string;stage?:string;message?:string;status?:MessageStatus;code?:string|null;message_id?:string;artifact?:OpenUIArtifact;citation?:Citation};
export type EvidenceResult = {id:string;run_id:string}&({kind:'search';data:SearchResponse}|{kind:'query';data:QueryResponse}|{kind:'schema';data:DatasetSchema}|{kind:'lineage';data:Lineage}|{kind:'attachment';data:AttachmentEvidence}|{kind:'proposal';data:CatalogProposal});
export interface PublicActor {subject:string;display_name:string;avatar_data_url:string|null;avatar_version:string|null}
export interface UserProfile {subject:string;display_name:string;locale:string;time_zone:string;response_language:string;avatar_url:string|null;avatar_version:string|null}
export type ProfileInput=Partial<Pick<UserProfile,'display_name'|'locale'|'time_zone'|'response_language'>>;
export interface Presentation {locale:string;time_zone:string;response_language:string}
export interface PersonalToken {id:string;name:string;tenant_id:string;prefix:string;scopes:string[];workspace_ids:string[]|null;asset_ids:string[]|null;expires_at:string;revoked_at:string|null;last_used_at:string|null;created_at:string}
export interface PersonalTokenInput {name:string;tenant_id:string;scopes:string[];expires_at:string;workspace_ids?:string[]|null;asset_ids?:string[]|null}
export interface CreatedPersonalToken extends PersonalToken {token:string}
export interface TokenScopeOptions {items:{id:string;name:string;dependencies:string[]}[];max_lifetime_days:number;max_active_per_user:number}
export interface DocumentChunk {id:string;index:number;total_chunks:number;text:string;char_start:number;char_end:number;page:number|null;section_path:string|null;embedding_model:string|null}
export interface ChunkFilter {offset?:number;limit?:number;page?:number;section?:string;q?:string;[key:string]:string|number|boolean|undefined}
export interface DocumentChunks {document_id:string;source_id:string;native_source_id:string;source_version_id?:string|null;extraction_id?:string|null;items:DocumentChunk[];offset:number;limit:number;total:number;next_offset:number|null}

export interface PageFilter {q?:string;page?:number;page_size?:number;sort?:string;order?:'asc'|'desc';[key:string]:string|number|boolean|undefined}
export interface StatusFilter extends PageFilter {status?:string}
export interface MemberUpdate {role?:Membership['role'];active?:boolean}
export interface Person {profile_id?:string|null;subject:string;display_name:string;avatar_url:string|null;avatar_version:string|null}
export interface ContentPrecondition {filename?:string;expected_sha256:string;acknowledge_chunk_invalidation?:boolean;expected_source_version_id?:string|null;expected_extraction_id?:string|null}
export interface ContentEffects {unchanged?:boolean;affected_asset_ids?:string[];snapshot_id?:string;file_id?:string;historical_snapshots_preserved?:boolean;citation_rows_preserved?:boolean;previous_chunk_ids_invalidated?:boolean;[key:string]:Json|undefined}
export interface ContentUpdate {asset:CatalogEntry;source?:CatalogEntry;table?:CatalogEntry;version:CatalogEntry;effects:ContentEffects}
export interface KnowledgeConnectionInput {domain:'documents'|'structured';role:string;workspace_id?:string|null;mode?:'provider'|'current_agent';provider_id?:string|null;model_id?:string|null;model_options?:ModelParameters;dimensions?:number|null;storage_dimensions?:number|null;space_id?:string|null;enabled?:boolean;expected_revision?:number}
export interface KnowledgeConnection {id:string;tenant_id:string;workspace_id:string|null;domain:'documents'|'structured';role:string;mode:'provider'|'current_agent';provider_id:string|null;model_id:string|null;model_options:Record<string,Json>;dimensions:number|null;storage_dimensions:number|null;space_id:string|null;embedding_fingerprint:string|null;enabled:boolean;revision:number;created_by:string;updated_by:string;created_at:string;updated_at:string}
export interface KnowledgeRole {id:string;domain:'documents'|'structured';label:string;kind:'embedding'|'generative';purposes:string[];supports_current_agent:boolean;compatible_index_required:boolean;assignment:'tenant'|'workspace'|null;status:'needs_setup'|'assigned'|'disabled';runtime_qualification:'not_run'}
export interface KnowledgeProvider {id:string;name:string;kind:ModelProvider['kind'];api:ModelApi|null;model_ids:string[];enabled:boolean}
export interface KnowledgeRoles {roles:KnowledgeRole[];model_options_schema:Record<string,Json>;providers?:KnowledgeProvider[]}

export interface ClarificationFrame {questions:string[];reasons:string[]}
export interface AgentUsage {agent:string;model:string|null;input_tokens:number;output_tokens:number;total_tokens:number;cost_usd:number;latency_ms:number;calls:number}
export interface UsageSummary {total_input_tokens:number;total_output_tokens:number;total_tokens:number;total_cost_usd:number;total_latency_ms:number;by_agent:AgentUsage[]}

export interface SourceUploadInput {file:Blob;filename?:string;workspace_id:string;project_id:string;parent_id:string;mode:'document'|'dataset'}

export interface DomainCapability {installed:boolean;registered:boolean;beans?:number;qualified?:boolean;reason?:string|null}

export interface AttachmentFilter {q?:string;kind?:'document'|'image'|'bundle';status?:'storing'|'queued'|'extracting'|'ready'|'failed'|'cancelled'|'expired'|'deleted';page?:number;page_size?:number;[key:string]:string|number|undefined}
export interface AttachmentChunkFilter {q?:string;page?:number;page_size?:number;[key:string]:string|number|undefined}

export interface IndexScope {workspace_id:string;domain:'documents'|'structured'}
export interface IndexFilter extends IndexScope {limit?:number;offset?:number;status?:string;dimensions?:number;model_id?:string;provider_kind?:string}
export type IdentityFilter = {q?:string;kind?:'keycloak'|'entra'|'google_workspace';status?:'draft'|'configured'|'blocked'|'verified'|'active'|'disabled';page?:number;page_size?:number}
export type IdentityGroupFilter = {q?:string;limit?:number;after?:string}
export type IdentityMappingFilter = {q?:string;status?:'all'|'enabled'|'disabled';workspace_id?:string;page?:number;page_size?:number}

export interface AttachmentEvidence {attachments:Array<{id:string;filename:string;media_type:string;sha256:string;revision:number;complete:boolean;chunk_ids:string[];total_chunks:number;warnings:string[]}>}
export interface ToolActivity {call_id:string;tool_name:'search_knowledge'|'inspect_schema'|'query_dataset'|'search_private_attachments'|'propose_catalog_update';status:'queued'|'running'|'completed'|'failed'|'cancelled';occurred_at:string;started_at?:string;finished_at?:string;duration_ms?:number;summary:string;result_id?:string}

export type ActivityFilter = {page?:number;page_size?:number};

export type ExportFilter = {q?:string;status?:'all'|'ready'|'cancelled'|'expired';page?:number;page_size?:number};
export type ShareFilter = {q?:string;status?:'all'|'active'|'revoked'|'expired';page?:number;page_size?:number};

export type AgentFilter = StatusFilter & {workspace_id?:string;project_id?:string};
