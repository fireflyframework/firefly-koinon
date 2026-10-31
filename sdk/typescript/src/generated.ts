// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Generated from source-backed standalone SDK wire schemas.
import type {Json} from './types.js';

export interface AddKnowledge {
 "expected_revision": number;
 "action": "add";
 "mode": "document" | "dataset";
 "workspace_id": string;
 "project_id": string;
 "parent_id": string;
}
export interface AnswerAudit {
 "run_id": string;
 "provenance_status": "recorded" | "not_recorded";
 "source_provenance_complete"?: boolean | null;
 "knowledge_settings_snapshot"?: OrganizationKnowledgeSnapshot | null;
 "generations"?: Array<GenerationReceipt>;
 "sources"?: Array<SourceReference>;
 "private_files"?: Array<PrivateFileReceipt>;
 "native_reads"?: Array<NativeReadReceipt>;
 "sql_attempts"?: Array<SqlAttemptReceipt>;
 "rlm_tools"?: Array<RlmToolReceipt> | null;
}
export interface AttachmentCapabilities {
 "storage": AttachmentObservation;
 "database": AttachmentObservation;
 "extraction": AttachmentObservation;
 "limits": AttachmentLimits;
 "formats": Array<AttachmentFormat>;
 "promotion": AttachmentPromotionRequirements;
}
export interface AttachmentFormat {
 "kind": "document" | "image" | "bundle";
 "media_type": string;
 "extensions": Array<string>;
 "extraction": AttachmentObservation;
}
export interface AttachmentHistorySummary {
 "id": string;
 "filename": string;
 "media_type": string;
 "kind": "document" | "image" | "bundle";
 "size_bytes": number;
 "sha256": string;
 "status": "storing" | "queued" | "extracting" | "ready" | "failed" | "cancelled" | "expired" | "deleted";
 "revision": number;
 "expires_at": string;
 "available": boolean;
}
export interface AttachmentLimits {
 "max_file_bytes": number;
 "max_image_bytes": number;
 "max_selected": number;
 "max_thread_files": number;
 "max_thread_bytes": number;
 "max_model_text_chars": number;
 "max_model_binary_bytes": number;
 "extraction_timeout_seconds": number;
 "ttl_seconds": number;
}
export interface AttachmentObservation {
 "available": boolean | null;
 "reason": string;
 "configured"?: boolean;
}
export interface AttachmentPage {
 "items": Array<AttachmentView>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
}
export interface AttachmentProgress {
 "status": "storing" | "queued" | "running" | "succeeded" | "failed" | "cancelled";
 "percent": number;
 "attempts": number;
}
export type AttachmentPromotionInput = AddKnowledge | ReplaceDocument | ReplaceTable;
export interface AttachmentPromotionRequirements {
 "ready_attachment"?: boolean;
 "ingest_write"?: boolean;
 "catalog_write"?: boolean;
 "document_sha256"?: boolean;
 "document_chunk_invalidation_acknowledgement"?: boolean;
 "table_snapshot_id"?: boolean;
}
export interface AttachmentPromotionView {
 "promotion_id": string;
 "attachment_id": string;
 "action": "add" | "replace_document" | "replace_table";
 "source"?: PromotedCatalogEntry | null;
 "assets"?: Array<PromotedCatalogEntry>;
 "asset"?: PromotedCatalogEntry | null;
 "table"?: PromotedCatalogEntry | null;
 "version"?: PromotedCatalogEntry | null;
 "effects"?: Record<string,Json>;
}
export interface AttachmentRevision {
 "expected_revision": number;
}
export interface AttachmentView {
 "id": string;
 "tenant_id": string;
 "thread_id": string;
 "filename": string;
 "media_type": string;
 "kind": "document" | "image" | "bundle";
 "size_bytes": number;
 "sha256": string;
 "status": "storing" | "queued" | "extracting" | "ready" | "failed" | "cancelled" | "expired" | "deleted";
 "revision": number;
 "created_at": string;
 "expires_at": string;
 "page_count"?: number | null;
 "chunk_count": number;
 "progress": AttachmentProgress;
 "error_code"?: string | null;
 "error"?: string | null;
 "warnings"?: Array<string>;
}
export interface AuditValue {
}
export interface AuthorizedApplication {
 "id": string;
 "client_id": string;
 "name": string;
 "resource": string;
 "tenant_id": string;
 "tenant_name": string;
 "workspace_id": string;
 "workspace_name": string;
 "scopes": Array<string>;
 "status": "active" | "expired" | "revoked";
 "connected_at": string;
 "expires_at": string;
 "last_used_at": string | null;
 "revoked_at": string | null;
}
export interface BrandingInputValues {
 "product_name"?: string;
 "assistant_name"?: string;
 "logo_light"?: string | null;
 "logo_dark"?: string | null;
 "symbol"?: string | null;
 "favicon"?: string | null;
 "palette"?: BrandingPalettes;
 "font_family"?: "Manrope";
}
export interface BrandingPalette {
 "surface": string;
 "canvas": string;
 "text": string;
 "muted": string;
 "line": string;
 "action": string;
 "action_text": string;
 "accent": string;
}
export interface BrandingPalettes {
 "light"?: BrandingPalette;
 "dark"?: BrandingPalette;
}
export interface BrandingResetInput {
 "expected_revision": number;
}
export interface BrandingValues {
 "product_name"?: string;
 "assistant_name"?: string;
 "logo_light"?: string | null;
 "logo_dark"?: string | null;
 "symbol"?: string | null;
 "favicon"?: string | null;
 "palette"?: BrandingPalettes;
 "font_family"?: "Manrope";
}
export interface CatalogProposal {
 "id": string;
 "run_id": string;
 "kind"?: "catalog";
 "status": "pending" | "applied" | "cancelled";
 "revision": number;
 "asset_id": string;
 "before": CatalogProposalBefore;
 "changes": CatalogProposalPatch;
 "expected_catalog_digest": string;
 "created_at": string;
 "applied_at"?: string | null;
 "cancelled_at"?: string | null;
}
export interface CatalogProposalBefore {
 "name": string;
 "description": string;
}
export interface CatalogProposalPatch {
 "name"?: string | null;
 "description"?: string | null;
}
export interface CommittedKnowledge {
 "status"?: "committed";
 "receipt": KnowledgeCommitReceipt;
}
export interface ConversationExportInput {
 "thread_id": string;
 "message_ids": Array<string>;
 "kind": "conversation";
 "format": "markdown" | "json";
 "include_evidence"?: boolean;
}
export interface ConversationIdentity {
 "product_name": string;
 "assistant_name": string;
 "branding_revision": number;
 "branding_origin": "deployment" | "organization";
 "branding_sha256": string;
}
export interface ConversationMessage {
 "id": string;
 "role": "user" | "assistant";
 "text": string;
 "status": "completed" | "failed" | "cancelled";
 "revision": string;
 "private_derived"?: boolean;
 "source_ids"?: Array<string>;
 "result_ids"?: Array<string>;
 "created_at"?: string | null;
 "presentation"?: EvidencePresentation | null;
}
export interface ConversationOrigin {
 "kind": "conversation";
 "thread_id": string;
 "message_ids": Array<string>;
}
export interface ConversationSnapshot {
 "thread_id": string;
 "tenant_id": string;
 "owner_subject": string;
 "title": string;
 "revision": string;
 "messages": Array<ConversationMessage>;
 "sources"?: Array<SourceReference>;
 "source_manifest_complete"?: boolean;
 "originating_token_ids"?: Array<string>;
 "identity"?: ConversationIdentity | null;
}
export interface CoordinateCellPosition {
 "row": number;
 "column": number;
}
export interface CoordinateCellRequest {
 "snapshot_id": string;
 "cells": Array<CoordinateCellPosition>;
}
export interface CoordinateColumnBinding {
 "output_position": number;
 "source_field_index": number | null;
 "source_path": Array<string | number>;
 "source_type": string | null;
 "header_cells": Array<CoordinateHeaderCell>;
}
export interface CoordinateDependency {
 "name": string;
 "version": string | null;
}
export interface CoordinateHeaderCell {
 "row": number;
 "column": number;
}
export interface CoordinatePage {
 "manifest": TableCoordinateManifest;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
 "has_next": boolean;
 "has_previous": boolean;
}
export interface CoordinateParserDecision {
 "name": string;
 "value": string | number | number | boolean | null;
}
export interface CoordinateRowRange {
 "output_start": number;
 "count": number;
 "source_start": number;
 "source_stride": number;
}
export interface CoordinateSourceCell {
 "output_row": number;
 "output_column": number;
 "source_row": number | null;
 "source_column": number | null;
 "source_path": Array<string | number>;
 "header_cells": Array<CoordinateHeaderCell>;
 "source_type": string | null;
}
export interface CorporatePresentationSummary {
 "name_source"?: "organization" | "personal";
 "avatar_source"?: "organization" | "personal";
 "provider_id"?: string | null;
 "provider_name"?: string | null;
 "status"?: "not_configured" | "not_bound" | "queued" | "running" | "current" | "stale" | "unavailable" | "conflict";
 "last_synced_at"?: string | null;
 "corporate_department"?: string | null;
}
export interface CorporateProfileFieldCapability {
 "field": "display_name" | "avatar" | "job_title" | "department" | "manager";
 "source": "directory" | "verified_claims" | "local" | "personal";
 "supported": boolean;
 "required_permissions"?: Array<string>;
 "code"?: string | null;
}
export interface CorporateProfileFieldObservation {
 "field": "display_name" | "avatar" | "job_title" | "department" | "manager";
 "source": "directory" | "verified_claims" | "local" | "personal";
 "status": "not_observed" | "current" | "empty" | "unavailable" | "unsupported" | "stale";
 "observed_at"?: string | null;
 "code"?: string | null;
}
export interface CorporateProfileRefresh {
 "tenant_id": string;
 "profile_id"?: string | null;
 "status": "not_configured" | "not_bound" | "queued" | "running" | "current" | "stale" | "unavailable" | "conflict";
 "snapshot_revision"?: number;
 "last_synced_at"?: string | null;
 "last_attempt_at"?: string | null;
}
export type CorporateProfileRefreshInput = Record<string,never>;
export interface CorporateProfileSyncPolicy {
 "interval_seconds"?: number;
 "allow_personal_overrides"?: boolean;
 "name_source"?: "directory" | "personal";
 "avatar_source"?: "directory" | "personal";
 "job_title_source"?: "directory" | "verified_claims" | "local";
 "unit_source"?: "directory" | "verified_claims" | "local";
 "manager_source"?: "directory" | "verified_claims" | "local";
 "google_department"?: "department" | "org_unit_path";
 "keycloak_attributes"?: KeycloakProfileAttributes;
}
export interface DatasetFileAppendResult {
 "dataset_id": string;
 "file_version_id": string;
 "filename": string;
 "sha256": string;
 "byte_size": number;
 "table_ids": Array<string>;
 "status": "ready";
}
export interface DocumentEvidence {
 "kind"?: "document_passage";
 "source": SourceReference;
}
export interface DocumentExtraction {
 "document_id": string;
 "catalog_source_id": string;
 "native_source_id": string;
 "source_version_id": string;
 "extraction_id": string;
 "purpose": string;
 "coverage": string;
 "normalized_sha256": string;
 "created_at": string;
 "predecessor_extraction_id"?: string | null;
}
export interface DocumentExtractionPage {
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
 "has_next": boolean;
 "has_previous": boolean;
 "items": Array<DocumentExtraction>;
}
export interface DocumentHistoryIdentity {
 "document_id": string;
 "catalog_source_id": string;
 "native_source_id": string;
}
export interface DocumentHistoryPagination {
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
 "has_next": boolean;
 "has_previous": boolean;
}
export interface DocumentKnowledgeBounds {
 "retrieval_top_k": KnowledgeIntegerBounds;
 "retrieval_per_query_k": KnowledgeIntegerBounds;
 "retrieval_rrf_k": KnowledgeIntegerBounds;
 "query_expansion_n": KnowledgeIntegerBounds;
 "answer_top_k": KnowledgeIntegerBounds;
 "rlm_max_iters": KnowledgeIntegerBounds;
 "rlm_sub_budget": KnowledgeIntegerBounds;
 "rlm_max_depth": KnowledgeIntegerBounds;
 "rlm_self_consistency": KnowledgeIntegerBounds;
}
export interface DocumentKnowledgeCapabilities {
 "answer_modes": Array<"rag" | "rlm">;
 "rlm_curated_knowledge_supported": boolean;
 "rlm_curated_knowledge_reason": "KNOWLEDGE_RLM_UNQUALIFIED";
 "rlm_model_role": "documents.rlm";
 "rlm_recorded_views_required": true;
 "rlm_recorded_views_reason": "RLM_DOCUMENT_VIEWS_REQUIRED";
 "bounds": DocumentKnowledgeBounds;
}
export interface DocumentKnowledgeSettings {
 "answer_mode": "rag" | "rlm";
 "retrieval_top_k": number;
 "retrieval_per_query_k": number;
 "retrieval_rrf_k": number;
 "query_expansion_enabled": boolean;
 "query_expansion_n": number;
 "answer_top_k": number;
 "rlm_max_iters": number;
 "rlm_sub_budget": number;
 "rlm_max_depth": number;
 "rlm_self_consistency": number;
 "rlm_extended_reasoning": boolean;
}
export interface DocumentPartContent {
 "document_id": string;
 "catalog_source_id": string;
 "native_source_id": string;
 "source_version_id": string;
 "extraction_id": string;
 "source_part_id": string;
 "kind": "chunk" | "page";
 "sha256": string;
 "text": string;
 "recorded_page"?: number | null;
 "page_basis": "recorded_loader";
 "raw_sha256": string;
 "normalized_sha256": string;
 "input_sha256": string;
}
export interface DocumentPartPage {
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
 "has_next": boolean;
 "has_previous": boolean;
 "items": Array<DocumentPartSummary>;
}
export interface DocumentPartSummary {
 "document_id": string;
 "catalog_source_id": string;
 "native_source_id": string;
 "source_version_id": string;
 "extraction_id": string;
 "source_part_id": string;
 "kind": "artifact" | "section" | "chunk" | "page";
 "ordinal": number;
 "sha256": string;
 "recorded_page"?: number | null;
 "page_basis"?: "recorded_loader" | null;
 "char_start"?: number | null;
 "char_end"?: number | null;
 "offset_basis"?: string | null;
 "created_at": string;
}
export interface DocumentVersion {
 "document_id": string;
 "catalog_source_id": string;
 "native_source_id": string;
 "source_version_id": string;
 "filename"?: string | null;
 "media_type"?: string | null;
 "sha256": string;
 "byte_size": number;
 "actor"?: string | null;
 "created_at": string;
 "predecessor_source_version_id"?: string | null;
}
export interface DocumentVersionPage {
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
 "has_next": boolean;
 "has_previous": boolean;
 "items": Array<DocumentVersion>;
}
export interface EntraCredential {
 "kind": "entra";
 "secret": string;
 "directory_secret"?: string | null;
}
export interface EntraSettings {
 "kind": "entra";
 "tenant_id": string;
 "client_id": string;
 "directory_client_id"?: string | null;
 "membership_mode"?: "direct" | "transitive";
}
export interface EvidenceManifest {
 "revision": string;
 "sources"?: Array<SourceReference>;
 "complete"?: boolean;
 "omissions"?: Array<string>;
}
export interface EvidencePresentation {
 "locale"?: string;
 "time_zone"?: string;
 "response_language"?: string;
}
export interface Export {
 "id": string;
 "kind": "conversation" | "query_result";
 "format": "markdown" | "json" | "parquet" | "csv" | "jsonl";
 "title": string;
 "status": "ready" | "cancelled" | "expired";
 "revision": string;
 "completeness": "selected_messages" | "bounded" | "unknown";
 "row_count"?: number | null;
 "truncated"?: boolean | null;
 "created_at": string;
 "expires_at": string;
}
export interface ExportCreate {
 "review_id": string;
 "expected_revision": string;
}
export interface ExportPage {
 "items": Array<Export>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
}
export interface ExportReview {
 "id": string;
 "revision": string;
 "kind": "conversation" | "query_result";
 "format": "markdown" | "json" | "parquet" | "csv" | "jsonl";
 "title": string;
 "message_count": number;
 "source_count": number;
 "row_count"?: number | null;
 "row_cap"?: number | null;
 "truncated"?: boolean | null;
 "completeness": "selected_messages" | "bounded" | "unknown";
 "messages"?: Array<ConversationMessage>;
 "sources"?: Array<SourceReference>;
 "source_manifest_complete"?: boolean;
 "result"?: StoredResult | null;
 "omissions"?: Array<string>;
 "expires_at": string;
 "identity"?: ConversationIdentity | null;
}
export type ExportReviewRequest = ConversationExportInput | QueryResultExportInput;
export interface ExternalFileCatalogEntry {
 "id": string;
 "tenant_id": string;
 "kind": string;
 "name": string;
 "parent_id": string | null;
 "workspace_id": string;
 "project_id": string | null;
 "description": string;
 "status": string;
 "created_by": string;
 "updated_by": string;
 "metadata": Record<string,Json>;
 "created_at": string;
 "updated_at": string;
}
export interface ExternalFileChunkInput {
 "index": number;
 "data_base64": string;
 "sha256": string;
}
export interface ExternalFileCleanupInput {
 "review_ids": Array<string>;
 "max_objects"?: number;
}
export interface ExternalFileCleanupResult {
 "reviews": Array<ExternalFileCleanupReview>;
}
export interface ExternalFileCleanupReview {
 "id": string;
 "status": "purging" | "purged";
 "processed_objects": number;
 "total_objects": number;
}
export interface ExternalFileReceipt {
 "source": ExternalFileCatalogEntry;
 "assets": Array<ExternalFileCatalogEntry>;
}
export interface ExternalFileReviewInput {
 "filename": string;
 "content_type"?: string | null;
 "mode": "document" | "dataset";
 "destination_id": string;
 "size_bytes": number;
 "sha256": string;
}
export interface ExternalFileReviewView {
 "id": string;
 "tenant_id": string;
 "revision": number;
 "authorization_digest": string;
 "status": "uploading" | "preview" | "ingesting" | "committed" | "cancelled" | "unresolved";
 "filename": string;
 "content_type": string | null;
 "mode": "document" | "dataset";
 "size_bytes": number;
 "sha256": string;
 "destination": KnowledgeDestination;
 "received_chunks": number;
 "total_chunks": number;
 "expires_at": string;
 "submitted_by": string;
 "credential_id": string;
 "application_id": string | null;
 "origin"?: "external_proposal";
 "authority"?: "unverified";
 "provider"?: null;
 "model"?: null;
 "source_id"?: string | null;
 "intake_status"?: string | null;
 "receipt"?: ExternalFileReceipt | null;
}
export interface ExternalProposalEvidence {
 "kind"?: "external_proposal";
 "text": string;
 "sha256": string;
 "submitted_by": string;
 "credential_id": string;
 "application_id"?: string | null;
 "source_receipt_ids"?: Array<string>;
 "recorded_at": string;
 "authority"?: "unverified";
 "provider"?: null;
 "model"?: null;
}
export interface ExternalProposalOrigin {
 "kind": "external_proposal";
 "source_receipt_ids"?: Array<string>;
}
export interface ExternalReviewDecision {
 "expected_revision": number;
 "authorization_digest": string;
 "nonce": string;
}
export interface ExternalReviewInput {
 "action": "create_draft" | "create_published" | "update_draft" | "update_published" | "publish_draft";
 "destination_id": string;
 "target_item_id"?: string | null;
 "expected_version"?: number | null;
 "content": KnowledgeContent;
 "source_receipt_ids"?: Array<string>;
}
export interface ExternalReviewView {
 "id": string;
 "review": KnowledgeIntent;
 "status": "preview" | "committing" | "committed" | "cancelled" | "stale" | "unresolved";
 "expires_at": string;
}
export interface Frozen {
}
export interface GenerationReceipt {
 "id": string;
 "start_sequence": number;
 "agent_id": string;
 "agent_revision": number;
 "provider_id": string;
 "provider_revision": number;
 "provider_kind": "ollama" | "openai" | "anthropic";
 "model_id": string;
 "model_class": string;
 "api": "chat" | "responses" | "messages";
 "binding_output_mode"?: "default" | "native" | null;
 "model_options_sha256"?: string | null;
 "started_at": string;
 "finished_at"?: string | null;
 "status"?: "started" | "completed" | "failed";
}
export interface GlossaryPage {
 "items": Array<GlossaryTermRead>;
 "total"?: number | null;
 "limit"?: number | null;
 "offset"?: number | null;
 "has_more"?: boolean | null;
}
export interface GlossaryTermCreate {
 "term": string;
 "definition": string;
 "synonyms"?: Array<string>;
 "tags"?: Array<string>;
 "related_columns"?: Array<string>;
 "related_metrics"?: Array<string>;
}
export interface GlossaryTermRead {
 "id": string;
 "tenant_id": string;
 "workspace_id": string;
 "term": string;
 "definition": string;
 "synonyms_json": Array<string>;
 "tags_json": Array<string>;
 "related_columns_json": Array<string>;
 "related_metrics_json": Array<string>;
 "created_at": string;
 "updated_at": string;
}
export interface GlossaryTermUpdate {
 "definition"?: string | null;
 "synonyms"?: Array<string> | null;
 "tags"?: Array<string> | null;
 "related_columns"?: Array<string> | null;
 "related_metrics"?: Array<string> | null;
}
export interface GoogleCredential {
 "kind": "google_workspace";
 "secret"?: string | null;
 "service_account_email"?: string | null;
 "private_key"?: string | null;
 "private_key_id"?: string | null;
 "delegated_admin"?: string | null;
}
export interface GoogleWorkspaceSettings {
 "kind": "google_workspace";
 "client_id": string;
 "hosted_domains": Array<string>;
 "customer_id"?: string | null;
 "membership_mode"?: "direct" | "transitive";
}
export interface IdentityActivation {
 "expected_revision": number;
 "validation_id": string;
}
export interface IdentityCheck {
 "id": string;
 "status": "unconfigured" | "unknown" | "passed" | "failed" | "blocked" | "not_run";
 "message": string;
 "supported"?: boolean | null;
 "verified"?: boolean;
 "available"?: boolean | null;
 "observed_at"?: string | null;
}
export interface IdentityGroup {
 "id": string;
 "provider_id": string;
 "name": string;
 "path"?: string | null;
 "membership_mode": "direct" | "transitive";
}
export interface IdentityGroupPage {
 "items": Array<IdentityGroup>;
 "next_cursor"?: string | null;
}
export interface IdentityMapping {
 "id": string;
 "tenant_id": string;
 "provider_id": string;
 "group_id": string;
 "group_name": string;
 "role": "viewer" | "analyst" | "editor" | "operator" | "admin";
 "workspace_id": string | null;
 "enabled": boolean;
 "revision": number;
}
export interface IdentityMappingInput {
 "group_id": string;
 "role": "viewer" | "analyst" | "editor" | "operator" | "admin";
 "workspace_id"?: string | null;
 "enabled"?: boolean;
 "expected_revision"?: number | null;
}
export interface IdentityMappingPage {
 "items": Array<IdentityMapping>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
}
export interface IdentityProvider {
 "id": string;
 "tenant_id": string;
 "kind": "keycloak" | "entra" | "google_workspace";
 "name": string;
 "canonical_issuer": string;
 "broker_alias": string | null;
 "ownership": "deployment" | "tenant";
 "revision": number;
 "policy_revision"?: number;
 "status": "draft" | "configured" | "blocked" | "verified" | "active" | "disabled";
 "credential_configured": boolean;
 "settings": KeycloakSettings | EntraSettings | GoogleWorkspaceSettings;
 "checks"?: Array<IdentityCheck>;
 "capabilities"?: Array<string>;
 "observed_at"?: string | null;
 "created_at"?: string | null;
 "updated_at"?: string | null;
 "created_by"?: string | null;
 "updated_by"?: string | null;
}
export interface IdentityProviderInput {
 "kind": "keycloak" | "entra" | "google_workspace";
 "name": string;
 "broker_alias"?: string | null;
 "settings": KeycloakSettings | EntraSettings | GoogleWorkspaceSettings;
 "credential"?: KeycloakCredential | EntraCredential | GoogleCredential | null;
 "credential_reference"?: string | null;
}
export interface IdentityProviderPage {
 "items": Array<IdentityProvider>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
}
export interface IdentityProviderPatch {
 "expected_revision": number;
 "name"?: string | null;
 "settings"?: KeycloakSettings | EntraSettings | GoogleWorkspaceSettings | null;
 "credential"?: KeycloakCredential | EntraCredential | GoogleCredential | null;
 "credential_reference"?: string | null;
}
export interface IdentityRevision {
 "expected_revision": number;
}
export interface IdentityValidation {
 "id": string;
 "candidate_revision": number;
 "expires_at": string;
 "checks": Array<IdentityCheck>;
 "status"?: "pending" | "verified" | "failed" | "consumed";
 "authorization_url"?: string | null;
}
export interface IndexActivateInput {
 "expected_revision": number;
 "expected_active_id": string | null;
 "expected_connection_revision": number | null;
 "recovery"?: "finish" | "restore_previous" | null;
}
export interface IndexCreateInput {
 "workspace_id": string;
 "domain": "documents" | "structured";
 "provider_id": string;
 "model_id": string;
 "expected_dimensions"?: number | null;
 "expected_active_id": string | null;
 "expected_connection_revision": number | null;
 "batch_size"?: number;
}
export interface IndexJobView {
 "index": KnowledgeIndexView;
 "job_id": string;
}
export interface IndexPage {
 "items": Array<KnowledgeIndexView>;
 "total": number;
 "limit": number;
 "offset": number;
}
export interface IndexPlanInput {
 "workspace_id": string;
 "domain": "documents" | "structured";
 "provider_id": string;
 "model_id": string;
 "expected_dimensions"?: number | null;
}
export interface IndexPlanView {
 "tenant_id": string;
 "workspace_id": string;
 "domain": "documents" | "structured";
 "provider_id": string;
 "provider_kind": string;
 "provider_revision": number;
 "model_id": string;
 "dimensions": number;
 "storage_dimensions": number;
 "qualification": string;
 "expected_connection_revision": number | null;
 "active_space_id": string | null;
 "active_index_id": string | null;
 "chunk_count": number;
 "warnings": Array<string>;
}
export interface IndexRevisionInput {
 "expected_revision": number;
}
export type Input = Record<string,never>;
export type JsonValue = Json;
export interface KeycloakCredential {
 "kind": "keycloak";
 "secret": string;
 "directory_secret"?: string | null;
}
export interface KeycloakProfileAttributes {
 "display_name"?: string | null;
 "job_title"?: string | null;
 "department"?: string | null;
 "manager"?: string | null;
 "picture"?: string | null;
}
export interface KeycloakSettings {
 "kind": "keycloak";
 "issuer": string;
 "client_id": string;
 "directory_client_id"?: string | null;
 "membership_mode"?: "direct" | "transitive";
}
export interface KnowledgeCancellation {
 "expected_revision": number;
}
export interface KnowledgeCommitReceipt {
 "operation_id": string;
 "intent_id": string;
 "intent_revision": number;
 "authorization_digest": string;
 "item_id": string;
 "native_item_id": string;
 "native_version_id": string;
 "version": number;
 "serving_version"?: number | null;
 "action": "create_draft" | "create_published" | "update_draft" | "update_published" | "publish_draft";
 "content_sha256": string;
 "evidence_sha256": string;
 "committed_at": string;
 "retrieval_state": "not_published" | "lexical_ready" | "indexing" | "ready" | "unavailable";
 "reason"?: string | null;
}
export interface KnowledgeConfirmation {
 "confirm": true;
 "expected_revision": number;
 "authorization_digest": string;
}
export interface KnowledgeContent {
 "title": string;
 "body": string;
 "summary"?: string | null;
 "domain"?: "legal" | "compliance" | "process" | "network" | "ai_platform" | "executive" | "hr" | "cto" | "engineering" | "security" | "other";
 "tags"?: Array<string>;
}
export interface KnowledgeDestination {
 "id": string;
 "workspace_id": string;
 "project_id": string;
 "name": string;
 "ancestry_digest": string;
}
export interface KnowledgeIndexView {
 "id": string;
 "tenant_id": string;
 "workspace_id": string;
 "domain": "documents" | "structured";
 "native_id": string;
 "space_id": string;
 "provider_kind": string;
 "model_id": string;
 "dimensions": number;
 "storage_dimensions": number;
 "status": string;
 "active": boolean;
 "revision": number;
 "job_id"?: string | null;
 "chunk_count": number;
 "vector_count": number;
 "indexed": boolean;
 "qualification": string;
 "recovery_required"?: boolean;
 "native_status"?: string | null;
 "provider_id"?: string | null;
 "created_by"?: string | null;
 "updated_by"?: string | null;
 "previous_space_id"?: string | null;
 "created_at"?: string | null;
 "ready_at"?: string | null;
 "activated_at"?: string | null;
 "retired_at"?: string | null;
 "error_code"?: string | null;
 "error"?: string | null;
}
export interface KnowledgeIntegerBounds {
 "minimum": number;
 "maximum": number;
}
export interface KnowledgeIntent {
 "id": string;
 "revision": number;
 "tenant_id": string;
 "owner_subject": string;
 "action": "create_draft" | "create_published" | "update_draft" | "update_published" | "publish_draft";
 "destination": KnowledgeDestination;
 "target_item_id": string;
 "expected_version"?: number | null;
 "before"?: KnowledgeContent | null;
 "after": KnowledgeContent;
 "evidence": Array<UserStatementEvidence | DocumentEvidence | StructuredEvidence | ExternalProposalEvidence>;
 "authorization_digest": string;
 "status": "preview" | "committing" | "committed" | "cancelled" | "stale" | "unresolved";
 "created_at": string;
 "expires_at": string;
 "receipt"?: KnowledgeCommitReceipt | null;
}
export interface KnowledgeIntentInput {
 "action": "create_draft" | "create_published" | "update_draft" | "update_published" | "publish_draft";
 "destination_id": string;
 "target_item_id"?: string | null;
 "expected_version"?: number | null;
 "content": KnowledgeContent;
 "origin": UserStatementOrigin | ConversationOrigin | ExternalProposalOrigin;
}
export interface KnowledgeItemPage {
 "items": Array<KnowledgeItemSummary>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
 "has_next": boolean;
 "has_previous": boolean;
}
export interface KnowledgeItemSummary {
 "id": string;
 "tenant_id": string;
 "workspace_id": string;
 "project_id": string;
 "destination_id": string;
 "title": string;
 "summary": string;
 "head_version": number;
 "serving_version"?: number | null;
}
export interface KnowledgeItemView {
 "id": string;
 "tenant_id": string;
 "workspace_id": string;
 "project_id": string;
 "destination_id": string;
 "head_version": number;
 "serving_version"?: number | null;
 "selected_version": KnowledgeVersionView;
}
export interface KnowledgeNumberBounds {
 "minimum": number;
 "maximum": number;
}
export type KnowledgePolicyValue = Record<string,never>;
export interface KnowledgeVersionView {
 "item_id": string;
 "version": number;
 "version_id": string;
 "publication": "draft" | "published";
 "serving": boolean;
 "content": KnowledgeContent;
 "evidence": Array<UserStatementEvidence | DocumentEvidence | StructuredEvidence | ExternalProposalEvidence>;
 "content_sha256": string;
 "evidence_sha256": string;
 "operation_id": string;
 "author_subject": string;
 "committed_at": string;
}
export interface McpConnectionDescriptor {
 "enabled": boolean;
 "local_only"?: boolean;
 "endpoint": string | null;
 "transport"?: "streamable-http";
 "authentication": Array<"personal_token" | "oauth">;
 "clients"?: Array<McpRegisteredClient>;
 "oauth_enabled": boolean;
 "oauth_registration": "pre_registered" | null;
 "supported_scopes": Array<string>;
 "tools": Array<McpToolCapability>;
 "review": McpReviewSupport;
 "client_acceptance"?: "not_verified";
}
export interface McpOAuthClient {
 "name": string;
 "redirect_uris": Array<string>;
 "scopes": Array<"catalog:read" | "catalog:write" | "ingest:write" | "knowledge:search" | "query:execute" | "chat:use" | "evidence:read">;
 "id": string;
 "tenant_id": string;
 "client_id": string;
 "client_type": "public" | "confidential";
 "enabled": boolean;
 "revision": number;
 "created_at": string;
 "updated_at": string;
 "created_by": string;
 "updated_by": string;
}
export interface McpOAuthClientCredential {
 "client": McpOAuthClient;
 "client_secret"?: string | null;
}
export interface McpOAuthClientInput {
 "name": string;
 "redirect_uris": Array<string>;
 "scopes": Array<"catalog:read" | "catalog:write" | "ingest:write" | "knowledge:search" | "query:execute" | "chat:use" | "evidence:read">;
 "client_type": "public" | "confidential";
}
export interface McpOAuthClientPage {
 "items": Array<McpOAuthClient>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
}
export interface McpOAuthClientPatch {
 "expected_revision": number;
 "name"?: string | null;
 "redirect_uris"?: Array<string> | null;
 "scopes"?: Array<"catalog:read" | "catalog:write" | "ingest:write" | "knowledge:search" | "query:execute" | "chat:use" | "evidence:read"> | null;
 "enabled"?: boolean | null;
}
export interface McpOAuthClientReadiness {
 "ready": boolean;
 "endpoint_enabled": boolean;
 "oauth_enabled": boolean;
 "encryption_configured": boolean;
 "missing_configuration": Array<"mcp_endpoint" | "oauth_enabled" | "oauth_encryption_key">;
 "static_clients_read_only"?: boolean;
}
export interface McpOAuthClientRevision {
 "expected_revision": number;
}
export interface McpOAuthClientValues {
 "name": string;
 "redirect_uris": Array<string>;
 "scopes": Array<"catalog:read" | "catalog:write" | "ingest:write" | "knowledge:search" | "query:execute" | "chat:use" | "evidence:read">;
}
export interface McpReadReceipt {
 "status": "recorded" | "not_recorded";
 "id"?: string | null;
 "sha256"?: string | null;
 "expires_at"?: string | null;
 "sources"?: Array<SourceReference>;
 "reason"?: "incomplete_or_unsupported_source_manifest" | "source_manifest_limit_or_missing_revision" | "receipt_byte_limit" | "active_receipt_limit" | "source_reuse_scope_required" | "capture_unavailable" | "transitive_lineage_unqualified" | "catalog_is_not_source_evidence" | null;
}
export interface McpRegisteredClient {
 "client_id": string;
 "name": string;
 "scopes": Array<string>;
 "client_auth": "public" | "confidential";
}
export interface McpReviewSupport {
 "supported": boolean;
 "mechanism"?: "mcp_apps";
 "resource_uri"?: "ui://koinon/knowledge-review";
 "mime_type"?: "text/html;profile=mcp-app";
 "external_redirect"?: false;
 "client_support"?: "not_observed";
}
export interface McpToolCapability {
 "name": string;
 "required_scopes": Array<string>;
 "access": "read" | "query" | "proposal" | "app_only";
 "requires_app"?: boolean;
}
export interface MessageSelection {
 "thread_id": string;
 "message_ids": Array<string>;
}
export interface NativeIndexChoice {
 "id": string;
 "tenant_id": string;
 "workspace_id": string;
 "domain": "documents" | "structured";
 "native_id": string;
 "space_id": string | null;
 "provider_kind": string | null;
 "model_id": string | null;
 "dimensions": number | null;
 "storage_dimensions": number;
 "status": string;
 "active": boolean;
 "chunk_count": number;
 "vector_count": number;
 "indexed": boolean | null;
 "qualification": string;
 "managed_id"?: string | null;
 "created_at"?: string | null;
 "ready_at"?: string | null;
 "activated_at"?: string | null;
 "retired_at"?: string | null;
}
export interface NativeIndexPage {
 "items": Array<NativeIndexChoice>;
 "total": number;
 "limit": number;
 "offset": number;
}
export interface NativeReadOrigin {
 "original_filename"?: string | null;
 "sheet_or_json_path"?: string | null;
 "connection_id"?: string | null;
 "connection_name"?: string | null;
 "database"?: string | null;
 "schema"?: string | null;
 "table"?: string | null;
}
export interface NativeReadReceipt {
 "result_id": string;
 "generation_id"?: string | null;
 "stage": string;
 "domain": "documents" | "structured" | "knowledge";
 "tenant_id": string;
 "workspace_id": string;
 "entity_id": string;
 "content_sha256": string;
 "source_ids"?: Array<string>;
 "snapshot_ids"?: Array<string>;
 "engine"?: string | null;
 "database"?: string | null;
 "catalog"?: string | null;
 "schema"?: string | null;
 "read_kind"?: "indexed_document" | "metadata" | "document_extraction" | "knowledge_version" | null;
 "origin"?: NativeReadOrigin | null;
 "source_version_id"?: string | null;
 "extraction_id"?: string | null;
 "knowledge_item_id"?: string | null;
 "knowledge_version_id"?: string | null;
 "knowledge_version"?: number | null;
}
export interface NativeTableSnapshot {
 "table_id": string;
 "table_name": string;
 "snapshot_id": string;
}
export interface OrganizationBranding {
 "tenant_id": string;
 "schema_version"?: 1;
 "revision": number;
 "origin": "deployment" | "organization";
 "branding": BrandingValues;
}
export interface OrganizationBrandingInput {
 "expected_revision": number;
 "branding": BrandingInputValues;
}
export interface OrganizationChatSettings {
 "tenant_id": string;
 "default_agent_id": string | null;
 "revision": number;
 "configured": boolean;
 "can_run": boolean;
 "status": "unconfigured" | "unavailable" | "disabled" | "needs_setup" | "unverified" | "ready";
}
export interface OrganizationChatSettingsInput {
 "default_agent_id": string | null;
 "expected_revision": number;
}
export interface OrganizationDirectorySettings {
 "tenant_id": string;
 "visibility"?: "administrators" | "shared_workspaces";
 "revision"?: number;
}
export interface OrganizationDirectorySettingsInput {
 "expected_revision": number;
 "visibility": "administrators" | "shared_workspaces";
}
export interface OrganizationKnowledgeCapabilities {
 "documents": DocumentKnowledgeCapabilities;
 "structured": StructuredKnowledgeCapabilities;
}
export interface OrganizationKnowledgeSettings {
 "tenant_id": string;
 "schema_version": 1;
 "revision": number;
 "origin": "deployment" | "organization";
 "documents": DocumentKnowledgeSettings;
 "structured": StructuredKnowledgeSettings;
 "capabilities": OrganizationKnowledgeCapabilities;
}
export interface OrganizationKnowledgeSettingsInput {
 "expected_revision": number;
 "documents": DocumentKnowledgeSettings;
 "structured": StructuredKnowledgeSettings;
}
export interface OrganizationKnowledgeSnapshot {
 "tenant_id": string;
 "schema_version": 1;
 "revision": number;
 "origin": "deployment" | "organization";
 "documents": DocumentKnowledgeSettings;
 "structured": StructuredKnowledgeSettings;
 "digest": string;
}
export interface OrganizationPerson {
 "id"?: string | null;
 "profile_id"?: string | null;
 "display_name": string;
 "avatar_url"?: string | null;
 "avatar_version"?: string | null;
 "job_title"?: string | null;
 "unit"?: OrganizationUnitSummary | null;
 "department"?: OrganizationUnitSummary | null;
 "manager"?: OrganizationPersonReference | null;
 "manager_unavailable"?: boolean;
 "revision"?: number;
 "source"?: "unassigned" | "manual" | "provider";
 "provider_id"?: string | null;
 "provider_name"?: string | null;
 "managed_fields"?: Array<"job_title" | "unit_id" | "manager_id">;
 "observed_at"?: string | null;
 "updated_at"?: string | null;
 "observation_status"?: "not_observed" | "current" | "unavailable";
 "presentation"?: CorporatePresentationSummary | null;
}
export interface OrganizationPersonCreate {
 "profile_id"?: string | null;
 "subject"?: string | null;
 "job_title"?: string | null;
 "unit_id"?: string | null;
 "manager_id"?: string | null;
}
export interface OrganizationPersonPage {
 "items": Array<OrganizationPerson>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
}
export interface OrganizationPersonPatch {
 "expected_revision": number;
 "job_title"?: string | null;
 "unit_id"?: string | null;
 "manager_id"?: string | null;
 "manage_locally"?: boolean;
 "managed_provider_id"?: string | null;
}
export interface OrganizationPersonReference {
 "id": string;
 "display_name": string;
}
export interface OrganizationPresentation {
 "name_source"?: "organization" | "personal";
 "avatar_source"?: "organization" | "personal";
 "provider_id"?: string | null;
 "provider_name"?: string | null;
 "status"?: "not_configured" | "not_bound" | "queued" | "running" | "current" | "stale" | "unavailable" | "conflict";
 "last_synced_at"?: string | null;
 "corporate_department"?: string | null;
 "tenant_id": string;
 "profile_id"?: string | null;
 "revision"?: number;
 "name_mode"?: "organization" | "personal";
 "avatar_mode"?: "organization" | "personal";
 "allow_personal_overrides"?: boolean;
 "display_name"?: string;
 "avatar_url"?: string | null;
 "avatar_version"?: string | null;
 "last_attempt_at"?: string | null;
 "fields"?: Array<CorporateProfileFieldObservation>;
}
export interface OrganizationPresentationInput {
 "expected_revision": number;
 "name_mode"?: "organization" | "personal";
 "avatar_mode"?: "organization" | "personal";
}
export interface OrganizationProfileFields {
 "job_title"?: string | null;
 "unit_external_key"?: string | null;
 "manager_external_subject"?: string | null;
}
export interface OrganizationProfileMapping {
 "tenant_id": string;
 "provider_id": string;
 "revision"?: number;
 "enabled"?: boolean;
 "fields"?: OrganizationProfileFields;
 "source"?: "verified_claims";
 "profile_sync"?: CorporateProfileSyncPolicy | null;
 "profile_capabilities"?: Array<CorporateProfileFieldCapability>;
}
export interface OrganizationProfileMappingInput {
 "expected_revision": number;
 "enabled": boolean;
 "fields": OrganizationProfileFields;
 "profile_sync"?: CorporateProfileSyncPolicy | null;
}
export interface OrganizationUnit {
 "id": string;
 "name": string;
 "kind": "division" | "department" | "team";
 "updated_at"?: string | null;
 "tenant_id": string;
 "parent_id"?: string | null;
 "revision": number;
 "provider_id"?: string | null;
 "has_children"?: boolean;
}
export interface OrganizationUnitInput {
 "name": string;
 "kind"?: "division" | "department" | "team";
 "parent_id"?: string | null;
 "provider_id"?: string | null;
 "external_key"?: string | null;
}
export interface OrganizationUnitPage {
 "items": Array<OrganizationUnit>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
}
export interface OrganizationUnitPatch {
 "expected_revision": number;
 "name"?: string | null;
 "kind"?: "division" | "department" | "team" | null;
 "parent_id"?: string | null;
}
export interface OrganizationUnitSummary {
 "id": string;
 "name": string;
 "kind": "division" | "department" | "team";
}
export interface Output {
}
export interface PendingKnowledgeCommit {
 "status"?: "pending";
 "operation_id": string;
 "intent_id": string;
 "reason"?: "commit_outcome_unresolved";
}
export interface PrivateChunkPage {
 "items": Array<PrivateChunkView>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
}
export interface PrivateChunkView {
 "id": string;
 "attachment_id": string;
 "index": number;
 "text": string;
 "page"?: number | null;
 "section_path": Array<string>;
 "char_start": number;
 "char_end": number;
 "offset_basis"?: "normalized_text_code_points";
 "sha256": string;
}
export interface PrivateFileReceipt {
 "id": string;
 "filename": string;
 "media_type": string;
 "sha256": string;
 "used_revision": number;
 "availability": "available" | "expired" | "deleted" | "changed" | "unavailable";
}
export interface PromotedCatalogEntry {
 "id": string;
 "tenant_id": string;
 "kind": string;
 "name": string;
 "parent_id": string | null;
 "workspace_id": string | null;
 "project_id": string | null;
 "description": string;
 "status": string;
 "created_by": string;
 "updated_by": string;
 "metadata": Record<string,Json>;
 "created_at": string;
 "updated_at": string;
}
export interface ProposalConfirmation {
 "confirm": true;
 "expected_revision": number;
}
export interface ProposalRevision {
 "expected_revision": number;
}
export interface ProposalUpdate {
 "id": string;
 "status": "applied" | "cancelled";
 "revision": number;
}
export interface ProvenanceArtifact {
 "id": string;
 "original_filename": string;
 "sha256": string;
 "byte_size": number;
 "file_format": string;
 "compression": string;
 "actor": string;
 "admitted_at": string;
}
export interface ProvenanceTransformStep {
 "id": string;
 "ordinal": number;
 "kind": string;
 "implementation": string;
 "implementation_sha256"?: string | null;
 "input_sha256"?: string | null;
 "output_sha256"?: string | null;
 "parameters"?: Record<string,Json>;
 "actor": string;
 "recorded_at": string;
}
export interface QueryResultExportInput {
 "kind": "query_result";
 "dataset_id": string;
 "query_id": string;
 "format": "parquet" | "csv" | "jsonl";
 "csv_mode"?: "spreadsheet_safe" | "exact";
}
export interface ReplaceDocument {
 "expected_source_version_id"?: string | null;
 "expected_extraction_id"?: string | null;
 "expected_revision": number;
 "action": "replace_document";
 "document_id": string;
 "expected_sha256": string;
 "acknowledge_chunk_invalidation": boolean;
}
export interface ReplaceTable {
 "expected_revision": number;
 "action": "replace_table";
 "dataset_id": string;
 "table_id": string;
 "expected_snapshot_id": string;
}
export interface ResultColumn {
 "name": string;
 "data_type": string;
}
export interface RlmToolReceipt {
 "result_id": string;
 "generation_id"?: string | null;
 "tenant_id": string;
 "workspace_id": string;
 "source_ids": Array<string>;
 "tool_call_id": string;
 "tool_name": "python" | "final_answer";
 "request_sha256": string;
 "schema_sha256": string;
 "arguments_sha256": string;
 "result_sha256": string;
 "result_kind": "tool_return" | "accepted_final" | "execution_failure";
 "execution_sha256": string;
 "outcome": "completed" | "rejected" | "failed" | "halted";
 "execution_status": string;
 "execution_state": string;
}
export interface Share {
 "id": string;
 "title": string;
 "revision": string;
 "status": "active" | "revoked" | "expired";
 "recipient_policy"?: "organization_current_acl";
 "created_at": string;
 "expires_at": string;
 "revoked_at"?: string | null;
}
export interface ShareCreate {
 "review_id": string;
 "expected_revision": string;
 "expires_in_hours"?: number;
 "recipient_policy"?: "organization_current_acl";
}
export interface SharePage {
 "items": Array<Share>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
}
export interface ShareReview {
 "id": string;
 "revision": string;
 "title": string;
 "message_count": number;
 "source_count": number;
 "messages": Array<ConversationMessage>;
 "sources": Array<SourceReference>;
 "source_manifest_complete": boolean;
 "recipient_policy"?: "organization_current_acl";
 "omissions"?: Array<string>;
 "expires_at": string;
 "identity"?: ConversationIdentity | null;
}
export interface ShareReviewInput {
 "thread_id": string;
 "message_ids": Array<string>;
}
export interface SharedConversation {
 "share": Share;
 "messages": Array<ConversationMessage>;
 "sources": Array<SourceReference>;
 "source_manifest_complete": boolean;
 "identity"?: ConversationIdentity | null;
}
export interface SourceReference {
 "id": string;
 "asset_id": string;
 "source_id"?: string | null;
 "title": string;
 "kind": "document" | "dataset" | "knowledge_version";
 "knowledge_item_id"?: string | null;
 "knowledge_version_id"?: string | null;
 "knowledge_version"?: number | null;
 "source_version_id"?: string | null;
 "extraction_id"?: string | null;
 "source_part_id"?: string | null;
 "source_part_sha256"?: string | null;
 "recorded_page"?: number | null;
 "page_basis"?: "recorded_loader" | null;
 "used_revision"?: string | null;
 "snapshot_id"?: string | null;
 "query_id"?: string | null;
 "chunk_id"?: string | null;
 "page"?: number | null;
 "section"?: string | null;
 "quote"?: string | null;
 "current_revision"?: string | null;
 "availability"?: "available" | "changed" | "unverified";
}
export interface SqlAttemptReceipt {
 "result_id": string;
 "generation_id"?: string | null;
 "ordinal": number;
 "stage": string;
 "statement_sha256": string;
 "statement"?: string | null;
 "classification"?: string | null;
 "outcome": string;
 "executed": boolean;
 "snapshot_pins"?: Record<string,string>;
 "row_count"?: number | null;
 "truncated"?: boolean | null;
 "reason_code"?: string | null;
 "engine"?: string | null;
 "database"?: string | null;
 "catalog"?: string | null;
 "schema"?: string | null;
 "execution_kind"?: "imported_snapshot" | "computed" | null;
 "dataset_id"?: string | null;
 "native_dataset_id"?: string | null;
 "tables"?: Array<NativeTableSnapshot>;
}
export interface StoredResult {
 "query_id": string;
 "asset_id": string;
 "revision": string;
 "row_count": number;
 "row_cap": number | null;
 "truncated": boolean | null;
 "completeness"?: "bounded" | "unknown";
 "byte_size": number;
 "columns"?: Array<ResultColumn>;
 "snapshot_ids"?: Array<string>;
 "snapshot_manifest_complete"?: boolean;
 "expires_at": string;
}
export interface StructuredEvidence {
 "kind"?: "structured_snapshot";
 "source": SourceReference;
}
export interface StructuredKnowledgeBounds {
 "top_k_schema": KnowledgeIntegerBounds;
 "top_k_examples": KnowledgeIntegerBounds;
 "top_k_metrics": KnowledgeIntegerBounds;
 "rrf_k": KnowledgeIntegerBounds;
 "generation_candidates": KnowledgeIntegerBounds;
 "max_refine_retries": KnowledgeIntegerBounds;
 "grounding_min_confidence": KnowledgeNumberBounds;
}
export interface StructuredKnowledgeCapabilities {
 "bounds": StructuredKnowledgeBounds;
}
export interface StructuredKnowledgeSettings {
 "top_k_schema": number;
 "top_k_examples": number;
 "top_k_metrics": number;
 "rrf_k": number;
 "generation_candidates": number;
 "max_refine_retries": number;
 "grounding_min_confidence": number;
}
export interface TableColumnBindingPage {
 "manifest": TableCoordinateManifest;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
 "has_next": boolean;
 "has_previous": boolean;
 "items": Array<CoordinateColumnBinding>;
}
export interface TableCoordinateManifest {
 "dataset_id": string;
 "table_id": string;
 "native_dataset_id": string;
 "native_table_id": string;
 "snapshot_id": string;
 "status": "complete" | "partial" | "not_recorded";
 "index_base"?: number;
 "row_count"?: number | null;
 "column_count"?: number | null;
 "artifact_id"?: string | null;
 "run_id"?: string | null;
 "input_sha256"?: string | null;
 "mapping_sha256"?: string | null;
 "source_format"?: string | null;
 "source_variant"?: string | null;
 "row_kind"?: "record" | "sheet_row" | "json_array" | "jsonl_record" | "single_object" | null;
 "source_sheet"?: string | null;
 "source_path"?: Array<string | number>;
 "parser_decisions"?: Array<CoordinateParserDecision>;
 "dependencies"?: Array<CoordinateDependency>;
 "reason_code"?: string | null;
 "rejected_source_rows"?: Array<number>;
}
export interface TableCoordinateSelection {
 "manifest": TableCoordinateManifest;
 "items": Array<CoordinateSourceCell>;
}
export interface TableProvenance {
 "dataset_id": string;
 "table_id": string;
 "native_dataset_id": string;
 "native_table_id": string;
 "snapshot_id": string;
 "status": "recorded" | "not_recorded";
 "snapshot_status": "PARTIAL" | "READY" | "FAILED";
 "level": "file_section";
 "operation"?: "upload" | "replace" | "reingest" | null;
 "predecessor_snapshot_id"?: string | null;
 "artifact"?: ProvenanceArtifact | null;
 "sheet_or_json_path"?: string | null;
 "table_label"?: string | null;
 "parquet_sha256"?: string | null;
 "parquet_byte_size"?: number | null;
 "schema_sha256"?: string | null;
 "row_count"?: number | null;
 "actor"?: string | null;
 "recorded_at"?: string | null;
 "run_id"?: string | null;
 "reader_implementation"?: string | null;
 "reader_sha256"?: string | null;
 "parser_parameters"?: Record<string,Json> | null;
 "steps"?: Array<ProvenanceTransformStep>;
}
export interface TableRowRangePage {
 "manifest": TableCoordinateManifest;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
 "has_next": boolean;
 "has_previous": boolean;
 "items": Array<CoordinateRowRange>;
}
export interface TableSnapshotPage {
 "items": Array<TableSnapshotSummary>;
 "total": number;
 "page": number;
 "page_size": number;
 "pages": number;
 "has_next": boolean;
 "has_previous": boolean;
 "current_snapshot_id": string | null;
}
export interface TableSnapshotSummary {
 "dataset_id": string;
 "table_id": string;
 "native_dataset_id": string;
 "native_table_id": string;
 "snapshot_id": string;
 "status": "recorded" | "not_recorded";
 "snapshot_status": "PARTIAL" | "READY" | "FAILED";
 "level": "file_section";
 "operation"?: "upload" | "replace" | "reingest" | null;
 "predecessor_snapshot_id"?: string | null;
 "artifact"?: ProvenanceArtifact | null;
 "sheet_or_json_path"?: string | null;
 "table_label"?: string | null;
 "parquet_sha256"?: string | null;
 "parquet_byte_size"?: number | null;
 "schema_sha256"?: string | null;
 "row_count"?: number | null;
 "actor"?: string | null;
 "recorded_at"?: string | null;
}
export interface UserStatementEvidence {
 "kind"?: "user_statement";
 "text": string;
 "sha256": string;
 "author_subject": string;
 "recorded_at": string;
 "authority"?: "user_authored";
}
export interface UserStatementOrigin {
 "kind": "user_statement";
}
export type AttachmentStatus = AttachmentView["status"];
export type AttachmentKind = AttachmentView["kind"];
