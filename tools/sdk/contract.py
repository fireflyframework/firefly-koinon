# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Publish explicit canonical SDK mappings with source hashes, without booting the app."""

import argparse
import ast
import hashlib
import inspect
import json
import sys
from pathlib import Path

from pydantic import BaseModel, TypeAdapter
from pydantic.json_schema import models_json_schema
from compatibility import qualified_glossary

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "sdk/python/src"))
from koinon_sdk import activity, communications
from koinon_sdk import contracts, models, indexes, identity, attachments, evidence, exports, sharing, proposals, glossary, answer_audit, provenance
from koinon_sdk.client import KoinonClient
from koinon_sdk import coordinates, curated, dataset_files, authorized_applications, organization_chat
from koinon_sdk import organization_knowledge
from koinon_sdk import organization_branding, mcp, external_reviews, external_file_reviews
from koinon_sdk import mcp_applications, document_history
from koinon_sdk import organization_people, corporate_profiles, memory, bulk, bulk_queries

rows = """
CommunicationsController.providers|communication_providers|communications.recipients.providers|-|RecipientProviderPage
CommunicationsController.recipients_search|communication_recipients|communications.recipients.list|-|DirectoryRecipientPage
CommunicationsController.preview|preview_email_invitation|communications.emailInvitations.preview|EmailInvitationInput|EmailPreview
CommunicationsController.create|create_email_invitation|communications.emailInvitations.create|EmailInvitationInput|EmailInvitation
CommunicationsController.page|email_invitations|communications.emailInvitations.list|-|EmailInvitationPage
CommunicationsController.revoke|revoke_email_invitation|communications.emailInvitations.revoke|-|void
CommunicationsController.resend|resend_email_invitation|communications.emailInvitations.resend|-|EmailInvitation
CommunicationsController.inspect|email_invitation|communications.emailInvitations.review|-|InvitationReview
CommunicationsController.accept|accept_email_invitation|communications.emailInvitations.accept|-|Membership
CommunicationsController.decline|decline_email_invitation|communications.emailInvitations.decline|-|InvitationReview
CommunicationsController.capabilities|communications_capabilities|communications.administration.capabilities|-|CommunicationCapabilities
CommunicationsController.policy|communications_policy|communications.administration.policy|-|CommunicationPolicy
CommunicationsController.policy_update|update_communications_policy|communications.administration.updatePolicy|CommunicationPolicyInput|CommunicationPolicy
CommunicationsController.deliveries|communication_deliveries|communications.administration.deliveries|-|DeliveryPage
CommunicationsController.delivery|communication_delivery|communications.administration.delivery|-|DeliveryRecord
CommunicationsController.retry|retry_communication_delivery|communications.administration.retry|-|DeliveryRecord
NotificationController.page|notifications|communications.notifications.list|-|OwnNotificationPage
NotificationController.unread_count|notification_unread_count|communications.notifications.unreadCount|-|NotificationUnreadCount
NotificationController.read|read_notification|communications.notifications.markRead|-|OwnNotification
NotificationController.preferences|notification_preferences|communications.notifications.preferences|-|NotificationPreferences
NotificationController.preferences_update|update_notification_preferences|communications.notifications.updatePreferences|NotificationPreferencesInput|NotificationPreferences
NotificationController.preferences_preview|preview_notification_schedule|communications.notifications.previewPreferences|NotificationPreferencesInput|DigestSchedulePreview
NotificationController.email_preview|preview_activity_email|communications.notifications.previewEmail|ActivityEmailPreviewInput|EmailPreview

QueryBatchController.capabilities|query_batch_capabilities|queryBatches.capabilities|-|QueryBatchCapabilities
QueryBatchController.create|create_query_batch|queryBatches.create|QueryBatchCreate|QueryBatchView
QueryBatchController.list|query_batches|queryBatches.list|-|QueryBatchPage
QueryBatchController.get|query_batch|queryBatches.get|-|QueryBatchView
QueryBatchController.items|query_batch_items|queryBatches.items|-|QueryBatchItemPage
QueryBatchController.result|query_batch_result|queryBatches.result|-|QueryBatchResult
QueryBatchController.cancel|cancel_query_batch|queryBatches.cancel|QueryBatchAction|QueryBatchCancellation
QueryBatchController.reconcile|reconcile_query_batch_item|queryBatches.reconcile|QueryBatchAction|QueryBatchView

FileBatchController.capabilities|file_batch_capabilities|fileBatches.capabilities|-|FileBatchCapabilities
FileBatchController.create|create_file_batch|fileBatches.create|FileBatchCreate|FileBatchView
FileBatchController.list|file_batches|fileBatches.list|-|FileBatchPage
FileBatchController.get|file_batch|fileBatches.get|-|FileBatchView
FileBatchController.items|file_batch_items|fileBatches.items|-|FileItemPage
FileBatchController.content|upload_file_batch_item|fileBatches.upload|BulkFileUpload|StagedFileReceipt
FileBatchController.receipt|file_batch_item_receipt|fileBatches.receipt|-|StagedFileReceipt
FileBatchController.submit|submit_file_batch|fileBatches.submit|BulkAction|FileBatchView
FileBatchController.cancel|cancel_file_batch|fileBatches.cancel|BulkAction|FileBatchView
FileBatchController.reconcile|reconcile_file_batch_item|fileBatches.reconcile|BulkAction|FileBatchView
FileBatchController.recover_original|reconcile_file_batch_original|fileBatches.recoverOriginal|BulkAction|FileBatchView

CorporateProfilesController.presentation|organization_presentation|corporateProfiles.presentation|-|OrganizationPresentation
CorporateProfilesController.update_presentation|update_organization_presentation|corporateProfiles.updatePresentation|OrganizationPresentationInput|OrganizationPresentation
CorporateProfilesController.refresh_self|refresh_organization_profile|corporateProfiles.refreshSelf|CorporateProfileRefreshInput|CorporateProfileRefresh
CorporateProfilesController.refresh_person|refresh_organization_person_profile|corporateProfiles.refreshPerson|CorporateProfileRefreshInput|CorporateProfileRefresh

OrganizationPeopleController.self|organization_person_self|organizationPeople.me|-|OrganizationPerson
OrganizationPeopleController.page|organization_people|organizationPeople.list|-|OrganizationPersonPage
OrganizationPeopleController.create|create_organization_person|organizationPeople.create|OrganizationPersonCreate|OrganizationPerson
OrganizationPeopleController.get|organization_person|organizationPeople.get|-|OrganizationPerson
OrganizationPeopleController.update|update_organization_person|organizationPeople.update|OrganizationPersonPatch|OrganizationPerson
OrganizationPeopleController.avatar|organization_person_avatar|organizationPeople.avatar|-|BinaryDownload
OrganizationPeopleController.reports|organization_person_reports|organizationPeople.reports|-|OrganizationPersonPage
OrganizationPeopleController.units|organization_units|organizationPeople.units|-|OrganizationUnitPage
OrganizationPeopleController.create_unit|create_organization_unit|organizationPeople.createUnit|OrganizationUnitInput|OrganizationUnit
OrganizationPeopleController.update_unit|update_organization_unit|organizationPeople.updateUnit|OrganizationUnitPatch|OrganizationUnit
OrganizationPeopleController.delete_unit|delete_organization_unit|organizationPeople.deleteUnit|-|void
OrganizationPeopleController.settings|organization_directory_settings|organizationPeople.settings|-|OrganizationDirectorySettings
OrganizationPeopleController.update_settings|update_organization_directory_settings|organizationPeople.updateSettings|OrganizationDirectorySettingsInput|OrganizationDirectorySettings
OrganizationPeopleController.mapping|organization_profile_mapping|organizationPeople.mapping|-|OrganizationProfileMapping
OrganizationPeopleController.update_mapping|update_organization_profile_mapping|organizationPeople.updateMapping|OrganizationProfileMappingInput|OrganizationProfileMapping

DocumentHistoryController.versions|document_versions|documents.versions|-|DocumentVersionPage
DocumentHistoryController.version|document_version|documents.version|-|DocumentVersion
DocumentHistoryController.extractions|document_extractions|documents.extractions|-|DocumentExtractionPage
DocumentHistoryController.parts|document_parts|documents.parts|-|DocumentPartPage
DocumentHistoryController.part|document_part|documents.part|-|DocumentPartContent
DocumentHistoryController.original|document_version_original|documents.versionOriginal|-|BinaryDownload

McpOAuthClientController.readiness|mcp_oauth_clients_readiness|mcpOAuthClients.readiness|-|McpOAuthClientReadiness
McpOAuthClientController.page|mcp_oauth_clients|mcpOAuthClients.list|-|McpOAuthClientPage
McpOAuthClientController.create|create_mcp_oauth_client|mcpOAuthClients.create|McpOAuthClientInput|McpOAuthClientCredential
McpOAuthClientController.retrieve|mcp_oauth_client|mcpOAuthClients.get|-|McpOAuthClient
McpOAuthClientController.update|update_mcp_oauth_client|mcpOAuthClients.update|McpOAuthClientPatch|McpOAuthClient
McpOAuthClientController.rotate_secret|rotate_mcp_oauth_client_secret|mcpOAuthClients.rotateSecret|McpOAuthClientRevision|McpOAuthClientCredential
McpOrganizationConnectionController.get|organization_mcp_connection|mcp.organizationConnection|-|McpConnectionDescriptor

ExternalFileReviewController.cleanup|cleanup_external_file_reviews|externalFileReviews.cleanup|ExternalFileCleanupInput|ExternalFileCleanupResult
ExternalFileReviewController.stage|stage_external_file_review|externalFileReviews.stage|ExternalFileReviewInput|ExternalFileReviewView
ExternalFileReviewController.get|external_file_review|externalFileReviews.get|-|ExternalFileReviewView
ExternalFileReviewController.chunk|upload_external_file_chunk|externalFileReviews.chunk|ExternalFileChunkInput|ExternalFileReviewView
ExternalFileReviewController.seal|seal_external_file_review|externalFileReviews.seal|-|ExternalFileReviewView
ExternalFileReviewController.approve|approve_external_file_review|externalFileReviews.approve|ExternalReviewDecision|ExternalFileReviewView
ExternalFileReviewController.cancel|cancel_external_file_review|externalFileReviews.cancel|ExternalReviewDecision|ExternalFileReviewView

McpConnectionController.get|mcp_connection|mcp.connection|-|McpConnectionDescriptor
ExternalKnowledgeReviewController.stage|stage_external_review|externalReviews.stage|ExternalReviewInput|ExternalReviewView
ExternalKnowledgeReviewController.get|external_review|externalReviews.get|-|ExternalReviewView
ExternalKnowledgeReviewController.approve|approve_external_review|externalReviews.approve|ExternalReviewDecision|KnowledgeCommitOutcome
ExternalKnowledgeReviewController.cancel|cancel_external_review|externalReviews.cancel|ExternalReviewDecision|ExternalReviewView

BrandingDefaultsController.defaults|branding_defaults|branding.defaults|-|BrandingValues
OrganizationBrandingController.get|organization_branding|branding.get|-|OrganizationBranding
OrganizationBrandingController.update|update_organization_branding|branding.update|OrganizationBrandingInput|OrganizationBranding
OrganizationBrandingController.reset|reset_organization_branding|branding.reset|BrandingResetInput|OrganizationBranding
OrganizationKnowledgeController.get|organization_knowledge_settings|organizationKnowledge.get|-|OrganizationKnowledgeSettings
OrganizationKnowledgeController.update|update_organization_knowledge_settings|organizationKnowledge.update|OrganizationKnowledgeSettingsInput|OrganizationKnowledgeSettings
OrganizationChatController.get|organization_chat_settings|organizationChat.get|-|OrganizationChatSettings
OrganizationChatController.update|update_organization_chat_settings|organizationChat.update|OrganizationChatSettingsInput|OrganizationChatSettings
AuthorizedApplicationController.list|authorized_applications|authorizedApplications.list|-|Page[AuthorizedApplication]
AuthorizedApplicationController.detail|authorized_application|authorizedApplications.get|-|AuthorizedApplication
AuthorizedApplicationController.revoke|revoke_authorized_application|authorizedApplications.revoke|-|void
DatasetFilesController.append|append_dataset_file|dataset.appendFile|DatasetFileUpload|DatasetFileAppendResult
TableCoordinateController.manifest|table_coordinates|dataset.tableCoordinates|-|TableCoordinateManifest
TableCoordinateController.cells|table_coordinate_cells|dataset.tableCoordinateCells|CoordinateCellRequest|TableCoordinateSelection
TableCoordinateController.rows|table_coordinate_rows|dataset.tableCoordinateRows|-|TableRowRangePage
TableCoordinateController.columns|table_coordinate_columns|dataset.tableCoordinateColumns|-|TableColumnBindingPage
CuratedKnowledgeController.preview|preview_knowledge|knowledgeIntents.preview|KnowledgeIntentInput|KnowledgeIntent
CuratedKnowledgeController.intent|knowledge_intent|knowledgeIntents.get|-|KnowledgeIntent
CuratedKnowledgeController.confirm|confirm_knowledge|knowledgeIntents.confirm|KnowledgeConfirmation|KnowledgeCommitOutcome
CuratedKnowledgeController.cancel|cancel_knowledge|knowledgeIntents.cancel|KnowledgeCancellation|KnowledgeIntent
CuratedKnowledgeController.list|knowledge_items|knowledgeItems.list|-|KnowledgeItemPage
CuratedKnowledgeController.get|knowledge_item|knowledgeItems.get|-|KnowledgeItemView
CuratedKnowledgeController.version|knowledge_version|knowledgeItems.version|-|KnowledgeItemView
TableProvenanceController.snapshot|table_provenance|dataset.tableProvenance|-|TableProvenance
TableProvenanceController.history|table_snapshots|dataset.tableSnapshots|-|TableSnapshotPage
AssistantController.audit|run_audit|chat.audit|-|AnswerAudit
CatalogProposalController.get|proposal|chat.proposals.get|-|CatalogProposal
CatalogProposalController.confirm|confirm_proposal|chat.proposals.confirm|ProposalConfirmation|CatalogProposal
CatalogProposalController.cancel|cancel_proposal|chat.proposals.cancel|ProposalRevision|CatalogProposal

ExportController.review|review_export|exports.review|ExportReviewRequest|ExportReview
ExportController.create|create_export|exports.create|ExportCreate|Export
ExportController.list|exports|exports.list|-|ExportPage
ExportController.get|export|exports.get|-|Export
ExportController.download|export_download|exports.download|-|BinaryDownload
ExportController.cancel|cancel_export|exports.cancel|-|void
ShareController.review|review_share|shares.review|ShareReviewInput|ShareReview
ShareController.create|create_share|shares.create|ShareCreate|Share
ShareController.list|shares|shares.list|-|SharePage
ShareController.get|share|shares.get|-|SharedConversation
ShareController.revoke|revoke_share|shares.revoke|-|void
EvidenceController.conversation|conversation_evidence|evidence.conversation|MessageSelection|EvidenceManifest

AssistantController.activities|run_activities|chat.activities|-|Page[ToolActivity]
ChatAttachmentsController.knowledge|promote_attachment|chat.attachments.promote|AttachmentPromotionInput|AttachmentPromotionView
ChatAttachmentsController.capabilities|attachment_capabilities|chat.attachments.capabilities|-|AttachmentCapabilities
ChatAttachmentsController.upload|upload_attachment|chat.attachments.upload|AttachmentUpload|AttachmentView
ChatAttachmentsController.list_files|attachments|chat.attachments.list|-|AttachmentPage
ChatAttachmentsController.get|attachment|chat.attachments.get|-|AttachmentView
ChatAttachmentsController.original|attachment_original|chat.attachments.original|-|BinaryDownload
ChatAttachmentsController.chunks|attachment_chunks|chat.attachments.chunks|-|PrivateChunkPage
ChatAttachmentsController.cancel|cancel_attachment|chat.attachments.cancel|AttachmentRevision|AttachmentView
ChatAttachmentsController.retry|retry_attachment|chat.attachments.retry|AttachmentRevision|AttachmentView
ChatAttachmentsController.delete|remove_attachment|chat.attachments.remove|-|void

ChatHistoryController.folders|folders|chat.folders.list|-|Page[ChatFolder]
ChatHistoryController.create_folder|create_folder|chat.folders.create|FolderCreate|ChatFolder
ChatHistoryController.folder|folder|chat.folders.get|-|ChatFolder
ChatHistoryController.patch_folder|update_folder|chat.folders.update|FolderPatch|ChatFolder
ChatHistoryController.delete_folder|delete_folder|chat.folders.delete|-|void
ChatHistoryController.thread|thread|chat.get|-|ChatThread
ChatHistoryController.patch_thread|update_thread|chat.update|ThreadPatch|ChatThread
ChatHistoryController.delete_thread|delete_thread|chat.delete|-|void
ChatHistoryController.title_suggestion|suggest_title|chat.suggestTitle|TitleRequest|TitleSuggestion
KnowledgeIndexesController.list_indexes|knowledge_indexes|knowledgeIndexes.list|-|IndexPage
KnowledgeIndexesController.choices|native_index_choices|knowledgeIndexes.choices|-|NativeIndexPage
KnowledgeIndexesController.choice|native_index_choice|knowledgeIndexes.choice|-|NativeIndexChoice
KnowledgeIndexesController.get|knowledge_index|knowledgeIndexes.get|-|KnowledgeIndexView
KnowledgeIndexesController.plan|plan_knowledge_index|knowledgeIndexes.plan|IndexPlanInput|IndexPlanView
KnowledgeIndexesController.create|create_knowledge_index|knowledgeIndexes.create|IndexCreateInput|IndexJobView
KnowledgeIndexesController.activate|activate_knowledge_index|knowledgeIndexes.activate|IndexActivateInput|KnowledgeIndexView
KnowledgeIndexesController.cancel|cancel_knowledge_index|knowledgeIndexes.cancel|IndexRevisionInput|KnowledgeIndexView
KnowledgeIndexesController.resume|resume_knowledge_index|knowledgeIndexes.resume|IndexRevisionInput|IndexJobView
CorporateIdentityController.list|identity_providers|identity.list|-|IdentityProviderPage
CorporateIdentityController.create|create_identity_provider|identity.create|IdentityProviderInput|IdentityProvider
CorporateIdentityController.get|identity_provider|identity.get|-|IdentityProvider
CorporateIdentityController.update|update_identity_provider|identity.update|IdentityProviderPatch|IdentityProvider
CorporateIdentityController.test|test_identity_provider|identity.test|IdentityRevision|IdentityValidation
CorporateIdentityController.test_status|identity_test_status|identity.testStatus|-|IdentityValidation
CorporateIdentityController.groups|identity_groups|identity.groups|-|IdentityGroupPage
CorporateIdentityController.mappings|identity_mappings|identity.mappings|-|IdentityMappingPage
CorporateIdentityController.mapping_create|create_identity_mapping|identity.createMapping|IdentityMappingInput|IdentityMapping
CorporateIdentityController.mapping_update|update_identity_mapping|identity.updateMapping|IdentityMappingInput|IdentityMapping
CorporateIdentityController.mapping_remove|remove_identity_mapping|identity.removeMapping|-|void
CorporateIdentityController.activate|activate_identity_provider|identity.activate|IdentityActivation|IdentityProvider
CorporateIdentityController.disable|disable_identity_provider|identity.disable|IdentityRevision|IdentityProvider

ActivityController.personal|personal_activity|activity.personal|ActivityWindow|ActivitySummary
ActivityController.administrative|administrative_activity|activity.administrative|ActivityWindow|ActivitySummary
AuditController.audit|audit|audit.list|-|Page[AuditEvent]
CatalogController.catalog_list|catalog|catalog.list|-|Page[CatalogEntry]
CatalogController.catalog_create|create|catalog.create|CatalogCreate|CatalogEntry
CatalogController.catalog_get|get|catalog.get|-|CatalogEntry
CatalogController.catalog_patch|update|catalog.update|CatalogUpdate|CatalogEntry
CatalogController.catalog_archive|archive|catalog.archive|-|CatalogEntry
CatalogController.catalog_restore|restore|catalog.restore|-|CatalogEntry
CatalogHierarchyController.move|move|catalog.move|CatalogMove|CatalogEntry
CatalogController.catalog_delete|delete|catalog.delete|-|void
ContextController.context|context|context|-|ContextResponse
JobController.list|jobs|jobs.list|-|Page[Job]
JobController.get|job|jobs.get|-|Job
JobController.cancel|cancel_job|jobs.cancel|-|Job
MembershipController.members|members|members.list|-|Page[Membership]
MembershipController.member_create|add_member|members.add|MemberInput|Membership
MembershipController.member_patch|update_member|members.update|MemberUpdate|Membership
MembershipController.member_delete|remove_member|members.remove|-|void
MembershipController.invitations_list|invitations|invitations.list|-|Page[Invitation]
MembershipController.invitation_create|create_invitation|invitations.create|InvitationInput|InvitationCreated
MembershipController.invitation_revoke|revoke_invitation|invitations.revoke|-|void
MembershipController.invitation_inspect|inspect_invitation|invitations.inspect|InvitationToken|InvitationPreview
MembershipController.invitation_redeem|redeem_invitation|invitations.redeem|InvitationToken|Membership
AgentController.agents|agents|agents.list|-|Page[AgentConfiguration]
AgentController.agent_create|create_agent|agents.create|AgentInput|AgentConfiguration
AgentController.agent_update|update_agent|agents.update|AgentInput|AgentConfiguration
AgentController.agent_validate|validate_agent|agents.validate|-|AgentConfiguration
AssistantController.threads|threads|chat.threads|-|Page[ChatThread]
AssistantController.thread_create|create_thread|chat.create|ThreadInput|ChatThread
AssistantController.messages|messages|chat.messages|-|Page[ChatMessage]
AssistantController.submit|submit_run|chat.submit|RunInput|ChatRun
AssistantController.cancel|cancel_run|chat.cancel|-|ChatRun
AssistantController.retry|retry_run|chat.retry|-|ChatRun
AssistantController.events|events|chat.events|-|StreamEvent
AssistantController.result|result|chat.result|-|EvidenceResult
ProviderController.configuration|configuration|configuration.get|-|Configuration
ProviderController.provider_create|create_provider|providers.create|ProviderInput|ModelProvider
ProviderController.provider_update|update_provider|providers.update|ProviderInput|ModelProvider
ProviderController.provider_validate|validate_provider|providers.validate|-|ValidationResult
KnowledgeConnectionsController.roles|knowledge_roles|knowledgeConnections.roles|-|KnowledgeRoles
KnowledgeConnectionsController.list_connections|knowledge_connections|knowledgeConnections.list|-|Page[KnowledgeConnection]
KnowledgeConnectionsController.create|create_knowledge_connection|knowledgeConnections.create|KnowledgeConnectionInput|KnowledgeConnection
KnowledgeConnectionsController.update|update_knowledge_connection|knowledgeConnections.update|KnowledgeConnectionInput|KnowledgeConnection
KnowledgeConnectionsController.get|knowledge_connection|knowledgeConnections.get|-|KnowledgeConnection
KnowledgeConnectionsController.delete|delete_knowledge_connection|knowledgeConnections.remove|-|Deleted
KnowledgeController.upload|upload|sources.uploadFile|SourceUpload|UploadResponse
KnowledgeController.search|search|search|SearchRequest|SearchResponse
KnowledgeController.query|query|query|QueryRequest|QueryResponse
KnowledgeController.schema|schema|dataset.schema|-|DatasetSchema
KnowledgeController.lineage|lineage|lineage|-|Lineage
KnowledgeController.document_chunks|document_chunks|documents.chunks|-|DocumentChunks
KnowledgeController.document_original|document_download|documents.download|-|BinaryDownload
ContentController.reingest_document|reingest_document|documents.reingest|DocumentReingestInput|ContentUpdate
ContentController.reingest_table|reingest_table|dataset.reingestTable|TableReingestInput|ContentUpdate
ContentController.document|replace_document|documents.replace|DocumentReplacement|ContentUpdate
ContentController.table|replace_table|dataset.replaceTable|TableReplacement|ContentUpdate
ProfileController.get|profile|profile.get|-|UserProfile
ProfileController.update|update_profile|profile.update|ProfileUpdate|UserProfile
ProfileController.avatar|avatar_download|profile.avatarDownload|-|BinaryDownload
ProfileController.set_avatar|set_avatar|profile.uploadAvatar|AvatarUpload|UserProfile
ProfileController.delete_avatar|delete_avatar|profile.deleteAvatar|-|UserProfile
ProfileController.people|people|people.list|-|Page[Person]
ProfileController.person_avatar|person_avatar|people.avatar|-|BinaryDownload
PersonalTokenController.list|tokens|tokens.list|-|Page[PersonalToken]
PersonalTokenController.scopes|token_scopes|tokens.scopes|-|TokenScopeOptions
PersonalTokenController.create|create_token|tokens.create|TokenInput|TokenCreated
PersonalTokenController.revoke|revoke_token|tokens.revoke|-|void
CapabilitiesController.capabilities|capabilities|capabilities|-|Capabilities
"""
mapping = {row.split("|")[0]: row.split("|")[1:] for row in rows.strip().splitlines() if row.strip()}
operations = []
errors = []


def name(value):
    return (
        value.id
        if isinstance(value, ast.Name)
        else value.attr
        if isinstance(value, ast.Attribute)
        else ""
    )


def literal(value):
    try:
        return ast.literal_eval(value)
    except (ValueError, TypeError):
        return ast.unparse(value)


for path in sorted((root / "backend/src/koinon").rglob("*.py")):
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        errors.append(str(path.relative_to(root)))
        continue
    for cls in [v for v in tree.body if isinstance(v, ast.ClassDef)]:
        decorators = [
            d.func if isinstance(d, ast.Call) else d for d in cls.decorator_list
        ]
        if not any(name(d) in ("rest_controller", "controller") for d in decorators):
            continue
        prefix = ""
        for d in cls.decorator_list:
            if isinstance(d, ast.Call) and name(d.func) == "request_mapping" and d.args:
                prefix = literal(d.args[0])
        for method in cls.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in method.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                verb = name(decorator.func).removesuffix("_mapping")
                if verb not in ("get", "post", "put", "patch", "delete"):
                    continue
                suffix = literal(decorator.args[0]) if decorator.args else ""
                full = prefix + suffix
                category = (
                    "gated_compatibility"
                    if full.startswith(("/api/v1/canon", "/api/v1/structured"))
                    else "canonical"
                    if full.startswith("/api/v1")
                    else "browser_auth"
                    if full.startswith("/auth")
                    else "public"
                )
                operations.append(
                    {
                        "method": verb.upper(),
                        "path": full,
                        "category": category,
                        "operation": cls.name + "." + method.name,
                        "source": str(path.relative_to(root)),
                        "line": method.lineno,
                        "parameters": [
                            {
                                "name": a.arg,
                                "annotation": ast.unparse(a.annotation)
                                if a.annotation
                                else None,
                            }
                            for a in method.args.args
                            if a.arg not in ("self", "request")
                        ],
                        "return_annotation": ast.unparse(method.returns)
                        if method.returns
                        else None,
                        "sdk_python": None,
                        "sdk_typescript": None,
                        "sdk_java": None,
                    }
                )

assert not errors, errors
inventory = {"operations": operations}
java_map_path = root / "sdk/java/src/test/resources/canonical-methods.json"
java_map = json.loads(java_map_path.read_text()) if java_map_path.exists() else {}
operations = []
unmapped = []
for op in inventory["operations"]:
    if op["category"] != "canonical":
        continue
    if op["operation"] not in mapping:
        unmapped.append(op["operation"])
        continue
    py, ts, request, response = mapping.pop(op["operation"])
    assert callable(getattr(KoinonClient, py)), py
    path = root / op["source"]
    tree = ast.parse(path.read_text())
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == op["operation"].split(".")[0]
    )
    method = next(
        node
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == op["operation"].split(".")[1]
    )
    decorator = next(
        d
        for d in method.decorator_list
        if isinstance(d, ast.Call)
        and isinstance(d.func, ast.Name)
        and d.func.id.endswith("_mapping")
    )
    status = next(
        (
            ast.literal_eval(k.value)
            for k in decorator.keywords
            if k.arg == "status_code"
        ),
        200,
    )
    op.update(
        sdk_python=py,
        sdk_typescript=ts,
        sdk_java=java_map.get(op["operation"]),
        request_schema=None if request == "-" else request,
        response_schema=response,
        success_status=status,
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    if ts.startswith("communications."):
        op["sdk_typescript_factory"] = "createCommunicationsApi"
        op["sdk_typescript_module"] = "@fireflyframework/koinon-sdk/communications"
    if op["operation"] in {"CuratedKnowledgeController.confirm", "ExternalKnowledgeReviewController.approve", "ExternalFileReviewController.approve"}:
        op["success_statuses"] = [200, 202]
    defaults = (
        {
            argument.arg: ast.literal_eval(default)
            for argument, default in zip(
                method.args.args[-len(method.args.defaults) :], method.args.defaults
            )
        }
        if method.args.defaults
        else {}
    )
    for parameter in op["parameters"]:
        annotation = parameter["annotation"] or ""
        parameter["location"] = (
            "query"
            if annotation.startswith("QueryParam[")
            else "path"
            if annotation.startswith("PathVar[")
            else "body"
        )
        parameter["required"] = parameter["name"] not in defaults
        if parameter["name"] in defaults:
            parameter["default"] = defaults[parameter["name"]]
    op["encoding"] = (
        "multipart/form-data"
        if request in {"SourceUpload", "DocumentReplacement", "TableReplacement", "AttachmentUpload", "DatasetFileUpload"}
        else "image/png|image/jpeg|image/webp"
        if request == "AvatarUpload"
        else "text/event-stream"
        if response == "StreamEvent"
        else "binary"
        if response == "BinaryDownload"
        else "application/octet-stream"
        if request == "BulkFileUpload"
        else "application/json"
    )
    op["headers"] = (
        ["If-Match (unquoted digest/snapshot helper argument; quoted wire header)"]
        if op["operation"].startswith("ContentController.")
        else ["Last-Event-ID (last fully processed opaque event ID)"]
        if response == "StreamEvent"
        else ["If-None-Match (optional; avatars only)"]
        if response == "BinaryDownload" and "avatar" in op["path"]
        else ["Idempotency-Key (required; caller-supplied stable operation key)"]
        if (op["operation"].startswith(("FileBatchController.", "QueryBatchController.")) and op["method"] != "GET") or op["operation"] in {"KnowledgeIndexesController.create", "KnowledgeIndexesController.resume", "ChatAttachmentsController.upload", "ChatAttachmentsController.retry", "ChatAttachmentsController.knowledge", "CuratedKnowledgeController.confirm", "DatasetFilesController.append", "ExternalKnowledgeReviewController.stage", "ExternalKnowledgeReviewController.approve", "ExternalFileReviewController.stage", "ExternalFileReviewController.approve", "CommunicationsController.create"}
        else []
    )
    if op["operation"] in {"ContentController.document", "ContentController.reingest_document"}:
        op["headers"].extend(["X-Koinon-Source-Version (optional UUID paired with extraction)", "X-Koinon-Extraction (optional ingestion UUID paired with source version)"])
    operations.append(op)
assert not mapping, mapping
assert not unmapped, "Canonical API operations awaiting typed SDK mapping: " + ", ".join(unmapped)

classes = {}
for module in (communications, activity, models, contracts, indexes, identity, attachments, evidence, exports, sharing, proposals, glossary, answer_audit, provenance, coordinates, curated, dataset_files, authorized_applications, organization_chat, organization_knowledge, organization_branding, mcp, external_reviews, external_file_reviews, mcp_applications, document_history, organization_people, corporate_profiles, memory, bulk, bulk_queries):
    classes.update(
        {
            name: value
            for name, value in vars(module).items()
            # Pydantic can cache parameterized RootModels in module globals.
            if name.isidentifier()
            and inspect.isclass(value)
            and issubclass(value, BaseModel)
            and value.__module__ == module.__name__
            and name not in {"ResponseModel", "InputModel"}
        }
    )
for op in operations:
    response = op["response_schema"]
    if response.startswith("Page["):
        item = response[5:-1]
        classes[response] = models.Page[classes[item]]
references, schemas = models_json_schema(
    [(value, "validation") for value in classes.values()],
    ref_template="#/$defs/{model}",
)
schemas["models"] = {
    name: references[(value, "validation")] for name, value in classes.items()
}
outcome = TypeAdapter(curated.KnowledgeCommitOutcome).json_schema(ref_template="#/$defs/{model}")
schemas["$defs"].update(outcome.pop("$defs", {}))
schemas["$defs"]["KnowledgeCommitOutcome"] = outcome
schemas["models"]["KnowledgeCommitOutcome"] = {"$ref": "#/$defs/KnowledgeCommitOutcome"}
schemas.update(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "copyright": "Copyright 2026 Firefly Software Foundation",
        "license": "Apache-2.0",
        "description": "Canonical wire DTOs. Unknown additive response fields are accepted. Exact domain decimals and unsafe integers remain strings.",
    }
)
schemas["$defs"].update(
    {
        "Deleted": {
            "type": "object",
            "required": ["deleted"],
            "properties": {"deleted": {"type": "boolean"}},
        },
        "BinaryDownload": {
            "description": "Authenticated HTTP binary response. SDK metadata wrapper includes bytes/blob, Content-Type, ETag, RFC5987 filename and not_modified. Only authorized avatar304 is accepted.",
            "type": "string",
            "contentEncoding": "binary",
        },
        "AttachmentUpload": {"type":"object", "required":["file"], "properties":{"file":{"type":"string", "contentEncoding":"binary"}}},
        "DatasetFileUpload": {"type":"object", "required":["file"], "additionalProperties":False, "properties":{"file":{"type":"string", "contentEncoding":"binary"}}},
        "BulkFileUpload": {"type":"string", "contentEncoding":"binary", "description":"Exact admitted original bytes, 1..134217728 bytes; raw application/octet-stream, never JSON/base64/multipart."},
        "AvatarUpload": {
            "type": "string",
            "contentEncoding": "binary",
            "description": "Raw PNG/JPEG/WebP, at most2MiB; server sanitizes to JPEG.",
        },
        "SourceUpload": {
            "type": "object",
            "required": ["file", "workspace_id", "project_id", "parent_id", "mode"],
            "properties": {
                "file": {"type": "string", "contentEncoding": "binary"},
                **{
                    name: {"type": "string"}
                    for name in ("workspace_id", "project_id", "parent_id")
                },
                "mode": {"enum": ["document", "dataset"]},
            },
        },
        "DocumentReplacement": {
            "type": "object",
            "required": ["file"],
            "properties": {
                "file": {"type": "string", "contentEncoding": "binary"},
                "acknowledge_chunk_invalidation": {
                    "enum": ["true", "false"],
                    "default": "false",
                },
            },
        },
        "TableReplacement": {
            "type": "object",
            "required": ["file"],
            "properties": {"file": {"type": "string", "contentEncoding": "binary"}},
        },
    }
)
result = {
    "format_version": 1,
    "copyright": "Copyright 2026 Firefly Software Foundation",
    "license": "Apache-2.0",
    "api_prefix": "/api/v1",
    "status": "Canonical API contract; development snapshot",
    "canonical_operation_count": len(operations),
    "qualified_compatibility_operations": qualified_glossary(root),
    "precision": {
        "safe_integer_limit": 9007199254740991,
        "exact_decimals": "decimal string",
        "unsafe_integers": "base10 string",
        "raw_data": "JSON number|string|boolean|null recursively; never coerce exact strings",
    },
    "authentication": {
        "headless": "caller-supplied bearer, fresh per request; renewal owned by caller",
        "browser": "same operation suffix under /bff/api/v1 with native cookie session and CSRF on writes",
        "tokens_management": "interactive verified identity required; PAT cannot mint or manage PATs",
        "applications_management": "interactive owner identity required; personal tokens and application credentials cannot approve or manage authorizations",
    },
    "semantics": {
        "writes": "no automatic retries; explicit chat client_request_id supports server idempotency",
        "null": "omitted provider secret preserves, explicit null clears; optional request fields preserve explicit null where server accepts it",
        "streams": "close/cancel consuming stream releases HTTP response; explicit cancel endpoint cancels durable run; no automatic reconnect",
        "preconditions": "content writes require current sha256/snapshot_id via If-Match; no forced overwrite helper",
        "paging": "honor only endpoint-declared query parameters; Page fields optional for items-only endpoints",
    },
    "excluded": [
        {
            "path": "/auth/me",
            "reason": "browser session introspection; headless SDK uses verified bearer/profile/context",
        },
        {
            "path": "/health,/ready",
            "reason": "public operator probes outside versioned API; deployment HTTP checks",
        },
        {
            "path": "/api/v1/canon/**,/api/v1/structured/**",
            "reason": "Retained routes are excluded except the explicit qualified_compatibility_operations list; operation admission depends on deployment prerequisites and current authority",
        },
    ],
    "operations": operations,
}
target = root / "sdk/contract"
target.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--check",
    action="store_true",
    help="Verify deterministic checked-in contract without writing",
)
arguments = parser.parse_args()
outputs = {
    "operations.json": json.dumps(result, indent=2) + "\n",
    "schemas.json": json.dumps(schemas, indent=2) + "\n",
}
drift = []
for filename, content in outputs.items():
    destination = target / filename
    if arguments.check:
        if not destination.exists() or destination.read_text() != content:
            drift.append(filename)
    else:
        destination.write_text(content)
if drift:
    raise SystemExit(
        "Contract drift: " + ", ".join(drift) + "; run python tools/sdk/contract.py"
    )
print(
    f"{'Verified' if arguments.check else 'Published'} {len(operations)} canonical operations and {len(schemas['$defs'])} DTO schemas"
)
