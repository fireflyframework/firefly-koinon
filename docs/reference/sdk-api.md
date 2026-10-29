# API and SDK reference

Python, Java and TypeScript expose the same canonical headless API. The table records concrete SDK methods; it does not count browser-only authentication or retained domain routes outside this contract.

This development contract contains 144 operations. Resource operations require the caller's current membership, permissions and resource scope. Bearer credentials also enforce their saved expiry and bounds. Authorized-application management requires a verified interactive user session; personal tokens and application credentials cannot manage authorizations. [Read about authorized applications](../guides/authorized-applications.md).

[Download the operation manifest](sdk-contract.json). The maintained generator checks source mappings and schemas without starting the backend.

| API operation | Python client | TypeScript client | Java client | Response |
| --- | --- | --- | --- | --- |
| `GET /api/v1/tenants/{tenant_id}/audit` | `audit` | `audit.list` | `client.audit.list` | `Page[AuditEvent]` |
| `GET /api/v1/tenants/{tenant_id}/catalog` | `catalog` | `catalog.list` | `client.catalog.list` | `Page[CatalogEntry]` |
| `POST /api/v1/tenants/{tenant_id}/catalog` | `create` | `catalog.create` | `client.catalog.create` | `CatalogEntry` |
| `GET /api/v1/tenants/{tenant_id}/catalog/{entry_id}` | `get` | `catalog.get` | `client.catalog.get` | `CatalogEntry` |
| `PATCH /api/v1/tenants/{tenant_id}/catalog/{entry_id}` | `update` | `catalog.update` | `client.catalog.update` | `CatalogEntry` |
| `POST /api/v1/tenants/{tenant_id}/catalog/{entry_id}/archive` | `archive` | `catalog.archive` | `client.catalog.archive` | `CatalogEntry` |
| `POST /api/v1/tenants/{tenant_id}/catalog/{entry_id}/restore` | `restore` | `catalog.restore` | `client.catalog.restore` | `CatalogEntry` |
| `DELETE /api/v1/tenants/{tenant_id}/catalog/{entry_id}` | `delete` | `catalog.delete` | `client.catalog.delete` | `void` |
| `GET /api/v1/context` | `context` | `context` | `client.platform.context` | `ContextResponse` |
| `GET /api/v1/tenants/{tenant_id}/jobs` | `jobs` | `jobs.list` | `client.jobs.list` | `Page[Job]` |
| `GET /api/v1/tenants/{tenant_id}/jobs/{job_id}` | `job` | `jobs.get` | `client.jobs.get` | `Job` |
| `POST /api/v1/tenants/{tenant_id}/jobs/{job_id}/cancel` | `cancel_job` | `jobs.cancel` | `client.jobs.cancel` | `Job` |
| `GET /api/v1/tenants/{tenant_id}/members` | `members` | `members.list` | `client.members.list` | `Page[Membership]` |
| `POST /api/v1/tenants/{tenant_id}/members` | `add_member` | `members.add` | `client.members.add` | `Membership` |
| `PATCH /api/v1/tenants/{tenant_id}/members/{member_id}` | `update_member` | `members.update` | `client.members.update` | `Membership` |
| `DELETE /api/v1/tenants/{tenant_id}/members/{member_id}` | `remove_member` | `members.remove` | `client.members.remove` | `void` |
| `GET /api/v1/tenants/{tenant_id}/invitations` | `invitations` | `invitations.list` | `client.invitations.list` | `Page[Invitation]` |
| `POST /api/v1/tenants/{tenant_id}/invitations` | `create_invitation` | `invitations.create` | `client.invitations.create` | `InvitationCreated` |
| `DELETE /api/v1/tenants/{tenant_id}/invitations/{invitation_id}` | `revoke_invitation` | `invitations.revoke` | `client.invitations.revoke` | `void` |
| `POST /api/v1/invitations/inspect` | `inspect_invitation` | `invitations.inspect` | `client.invitationAccess.inspect` | `InvitationPreview` |
| `POST /api/v1/invitations/redeem` | `redeem_invitation` | `invitations.redeem` | `client.invitationAccess.redeem` | `Membership` |
| `GET /api/v1/tenants/{tenant_id}/agents` | `agents` | `agents.list` | `client.agents.list` | `Page[AgentConfiguration]` |
| `POST /api/v1/tenants/{tenant_id}/agents` | `create_agent` | `agents.create` | `client.agents.create` | `AgentConfiguration` |
| `PATCH /api/v1/tenants/{tenant_id}/agents/{agent_id}` | `update_agent` | `agents.update` | `client.agents.update` | `AgentConfiguration` |
| `POST /api/v1/tenants/{tenant_id}/agents/{agent_id}/validate` | `validate_agent` | `agents.validate` | `client.agents.validate` | `AgentConfiguration` |
| `GET /api/v1/tenants/{tenant_id}/chat/threads` | `threads` | `chat.threads` | `client.chat.threads` | `Page[ChatThread]` |
| `POST /api/v1/tenants/{tenant_id}/chat/threads` | `create_thread` | `chat.create` | `client.chat.createThread` | `ChatThread` |
| `GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/messages` | `messages` | `chat.messages` | `client.chat.messages` | `Page[ChatMessage]` |
| `POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/runs` | `submit_run` | `chat.submit` | `client.chat.submit` | `ChatRun` |
| `POST /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/cancel` | `cancel_run` | `chat.cancel` | `client.chat.cancel` | `ChatRun` |
| `POST /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/retry` | `retry_run` | `chat.retry` | `client.chat.retry` | `ChatRun` |
| `GET /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/events` | `events` | `chat.events` | `client.chat.events` | `StreamEvent` |
| `GET /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/results/{result_id}` | `result` | `chat.result` | `client.chat.result` | `EvidenceResult` |
| `GET /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/activity` | `run_activities` | `chat.activities` | `client.chat.activities` | `Page[ToolActivity]` |
| `GET /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/audit` | `run_audit` | `chat.audit` | `client.chat.audit` | `AnswerAudit` |
| `GET /api/v1/tenants/{tenant_id}/chat/folders` | `folders` | `chat.folders.list` | `client.chatFolders.list` | `Page[ChatFolder]` |
| `POST /api/v1/tenants/{tenant_id}/chat/folders` | `create_folder` | `chat.folders.create` | `client.chatFolders.create` | `ChatFolder` |
| `GET /api/v1/tenants/{tenant_id}/chat/folders/{folder_id}` | `folder` | `chat.folders.get` | `client.chatFolders.get` | `ChatFolder` |
| `PATCH /api/v1/tenants/{tenant_id}/chat/folders/{folder_id}` | `update_folder` | `chat.folders.update` | `client.chatFolders.update` | `ChatFolder` |
| `DELETE /api/v1/tenants/{tenant_id}/chat/folders/{folder_id}` | `delete_folder` | `chat.folders.delete` | `client.chatFolders.delete` | `void` |
| `GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}` | `thread` | `chat.get` | `client.chat.get` | `ChatThread` |
| `PATCH /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}` | `update_thread` | `chat.update` | `client.chat.update` | `ChatThread` |
| `POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/title-suggestion` | `suggest_title` | `chat.suggestTitle` | `client.chat.suggestTitle` | `TitleSuggestion` |
| `GET /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/proposals/{proposal_id}` | `proposal` | `chat.proposals.get` | `client.chatProposals.get` | `CatalogProposal` |
| `POST /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/proposals/{proposal_id}/confirm` | `confirm_proposal` | `chat.proposals.confirm` | `client.chatProposals.confirm` | `CatalogProposal` |
| `POST /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/proposals/{proposal_id}/cancel` | `cancel_proposal` | `chat.proposals.cancel` | `client.chatProposals.cancel` | `CatalogProposal` |
| `GET /api/v1/tenants/{tenant_id}/configuration` | `configuration` | `configuration.get` | `client.configuration.get` | `Configuration` |
| `POST /api/v1/tenants/{tenant_id}/providers` | `create_provider` | `providers.create` | `client.providers.create` | `ModelProvider` |
| `PUT /api/v1/tenants/{tenant_id}/providers/{provider_id}` | `update_provider` | `providers.update` | `client.providers.update` | `ModelProvider` |
| `POST /api/v1/tenants/{tenant_id}/providers/{provider_id}/validate` | `validate_provider` | `providers.validate` | `client.providers.validate` | `ValidationResult` |
| `GET /api/v1/authorized-applications` | `authorized_applications` | `authorizedApplications.list` | `client.authorizedApplications.list` | `Page[AuthorizedApplication]` |
| `GET /api/v1/authorized-applications/{application_id}` | `authorized_application` | `authorizedApplications.get` | `client.authorizedApplications.get` | `AuthorizedApplication` |
| `DELETE /api/v1/authorized-applications/{application_id}` | `revoke_authorized_application` | `authorizedApplications.revoke` | `client.authorizedApplications.revoke` | `void` |
| `GET /api/v1/tenants/{tenant_id}/identity/providers` | `identity_providers` | `identity.list` | `client.identity.list` | `IdentityProviderPage` |
| `POST /api/v1/tenants/{tenant_id}/identity/providers` | `create_identity_provider` | `identity.create` | `client.identity.create` | `IdentityProvider` |
| `GET /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}` | `identity_provider` | `identity.get` | `client.identity.get` | `IdentityProvider` |
| `PATCH /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}` | `update_identity_provider` | `identity.update` | `client.identity.update` | `IdentityProvider` |
| `POST /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/test` | `test_identity_provider` | `identity.test` | `client.identity.test` | `IdentityValidation` |
| `GET /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/tests/{validation_id}` | `identity_test_status` | `identity.testStatus` | `client.identity.testStatus` | `IdentityValidation` |
| `GET /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/groups` | `identity_groups` | `identity.groups` | `client.identity.groups` | `IdentityGroupPage` |
| `GET /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/mappings` | `identity_mappings` | `identity.mappings` | `client.identity.mappings` | `IdentityMappingPage` |
| `POST /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/mappings` | `create_identity_mapping` | `identity.createMapping` | `client.identity.createMapping` | `IdentityMapping` |
| `PATCH /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/mappings/{mapping_id}` | `update_identity_mapping` | `identity.updateMapping` | `client.identity.updateMapping` | `IdentityMapping` |
| `DELETE /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/mappings/{mapping_id}` | `remove_identity_mapping` | `identity.removeMapping` | `client.identity.removeMapping` | `void` |
| `POST /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/activate` | `activate_identity_provider` | `identity.activate` | `client.identity.activate` | `IdentityProvider` |
| `POST /api/v1/tenants/{tenant_id}/identity/providers/{provider_id}/disable` | `disable_identity_provider` | `identity.disable` | `client.identity.disable` | `IdentityProvider` |
| `POST /api/v1/tenants/{tenant_id}/evidence/conversations` | `conversation_evidence` | `evidence.conversation` | `client.evidence.conversation` | `EvidenceManifest` |
| `POST /api/v1/tenants/{tenant_id}/exports/reviews` | `review_export` | `exports.review` | `client.exports.review` | `ExportReview` |
| `POST /api/v1/tenants/{tenant_id}/exports` | `create_export` | `exports.create` | `client.exports.create` | `Export` |
| `GET /api/v1/tenants/{tenant_id}/exports` | `exports` | `exports.list` | `client.exports.list` | `ExportPage` |
| `GET /api/v1/tenants/{tenant_id}/exports/{export_id}` | `export` | `exports.get` | `client.exports.get` | `Export` |
| `GET /api/v1/tenants/{tenant_id}/exports/{export_id}/download` | `export_download` | `exports.download` | `client.exports.download` | `BinaryDownload` |
| `DELETE /api/v1/tenants/{tenant_id}/exports/{export_id}` | `cancel_export` | `exports.cancel` | `client.exports.cancel` | `void` |
| `GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/capabilities` | `attachment_capabilities` | `chat.attachments.capabilities` | `client.chatAttachments.capabilities` | `AttachmentCapabilities` |
| `POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments` | `upload_attachment` | `chat.attachments.upload` | `client.chatAttachments.upload` | `AttachmentView` |
| `GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments` | `attachments` | `chat.attachments.list` | `client.chatAttachments.list` | `AttachmentPage` |
| `GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}` | `attachment` | `chat.attachments.get` | `client.chatAttachments.get` | `AttachmentView` |
| `GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}/original` | `attachment_original` | `chat.attachments.original` | `client.chatAttachments.original` | `BinaryDownload` |
| `GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}/chunks` | `attachment_chunks` | `chat.attachments.chunks` | `client.chatAttachments.chunks` | `PrivateChunkPage` |
| `POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}/cancel` | `cancel_attachment` | `chat.attachments.cancel` | `client.chatAttachments.cancel` | `AttachmentView` |
| `POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}/retry` | `retry_attachment` | `chat.attachments.retry` | `client.chatAttachments.retry` | `AttachmentView` |
| `DELETE /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}` | `remove_attachment` | `chat.attachments.remove` | `client.chatAttachments.remove` | `void` |
| `POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}/knowledge` | `promote_attachment` | `chat.attachments.promote` | `client.chatAttachments.promote` | `AttachmentPromotionView` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-roles` | `knowledge_roles` | `knowledgeConnections.roles` | `client.knowledgeConnections.roles` | `KnowledgeRoles` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-connections` | `knowledge_connections` | `knowledgeConnections.list` | `client.knowledgeConnections.list` | `Page[KnowledgeConnection]` |
| `POST /api/v1/tenants/{tenant_id}/knowledge-connections` | `create_knowledge_connection` | `knowledgeConnections.create` | `client.knowledgeConnections.create` | `KnowledgeConnection` |
| `PUT /api/v1/tenants/{tenant_id}/knowledge-connections/{connection_id}` | `update_knowledge_connection` | `knowledgeConnections.update` | `client.knowledgeConnections.update` | `KnowledgeConnection` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-connections/{connection_id}` | `knowledge_connection` | `knowledgeConnections.get` | `client.knowledgeConnections.get` | `KnowledgeConnection` |
| `DELETE /api/v1/tenants/{tenant_id}/knowledge-connections/{connection_id}` | `delete_knowledge_connection` | `knowledgeConnections.remove` | `client.knowledgeConnections.remove` | `Deleted` |
| `POST /api/v1/tenants/{tenant_id}/sources/upload` | `upload` | `sources.uploadFile` | `client.sources.upload` | `UploadResponse` |
| `POST /api/v1/tenants/{tenant_id}/search` | `search` | `search` | `client.knowledge.search` | `SearchResponse` |
| `POST /api/v1/tenants/{tenant_id}/query` | `query` | `query` | `client.knowledge.query` | `QueryResponse` |
| `GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/schema` | `schema` | `dataset.schema` | `client.datasets.schema` | `DatasetSchema` |
| `GET /api/v1/tenants/{tenant_id}/lineage` | `lineage` | `lineage` | `client.knowledge.lineage` | `Lineage` |
| `GET /api/v1/tenants/{tenant_id}/documents/{document_id}/chunks` | `document_chunks` | `documents.chunks` | `client.documents.chunks` | `DocumentChunks` |
| `GET /api/v1/tenants/{tenant_id}/documents/{document_id}/original` | `document_download` | `documents.download` | `client.documents.original` | `BinaryDownload` |
| `POST /api/v1/tenants/{tenant_id}/documents/{document_id}/reingest` | `reingest_document` | `documents.reingest` | `client.documents.reingest` | `ContentUpdate` |
| `POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/reingest` | `reingest_table` | `dataset.reingestTable` | `client.datasets.reingestTable` | `ContentUpdate` |
| `POST /api/v1/tenants/{tenant_id}/documents/{document_id}/content` | `replace_document` | `documents.replace` | `client.documents.replace` | `ContentUpdate` |
| `POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/content` | `replace_table` | `dataset.replaceTable` | `client.datasets.replaceTable` | `ContentUpdate` |
| `POST /api/v1/tenants/{tenant_id}/knowledge-intents` | `preview_knowledge` | `knowledgeIntents.preview` | `client.knowledgeIntents.preview` | `KnowledgeIntent` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-intents/{intent_id}` | `knowledge_intent` | `knowledgeIntents.get` | `client.knowledgeIntents.get` | `KnowledgeIntent` |
| `POST /api/v1/tenants/{tenant_id}/knowledge-intents/{intent_id}/confirm` | `confirm_knowledge` | `knowledgeIntents.confirm` | `client.knowledgeIntents.confirm` | `KnowledgeCommitOutcome` |
| `POST /api/v1/tenants/{tenant_id}/knowledge-intents/{intent_id}/cancel` | `cancel_knowledge` | `knowledgeIntents.cancel` | `client.knowledgeIntents.cancel` | `KnowledgeIntent` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-items` | `knowledge_items` | `knowledgeItems.list` | `client.knowledgeItems.list` | `KnowledgeItemPage` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-items/{item_id}` | `knowledge_item` | `knowledgeItems.get` | `client.knowledgeItems.get` | `KnowledgeItemView` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-items/{item_id}/versions/{version}` | `knowledge_version` | `knowledgeItems.version` | `client.knowledgeItems.version` | `KnowledgeItemView` |
| `POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/files` | `append_dataset_file` | `dataset.appendFile` | `client.datasets.appendFile` | `DatasetFileAppendResult` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-indexes` | `knowledge_indexes` | `knowledgeIndexes.list` | `client.knowledgeIndexes.list` | `IndexPage` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-index-choices` | `native_index_choices` | `knowledgeIndexes.choices` | `client.knowledgeIndexes.choices` | `NativeIndexPage` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-index-choices/{choice_id}` | `native_index_choice` | `knowledgeIndexes.choice` | `client.knowledgeIndexes.choice` | `NativeIndexChoice` |
| `GET /api/v1/tenants/{tenant_id}/knowledge-indexes/{index_id}` | `knowledge_index` | `knowledgeIndexes.get` | `client.knowledgeIndexes.get` | `KnowledgeIndexView` |
| `POST /api/v1/tenants/{tenant_id}/knowledge-indexes/plan` | `plan_knowledge_index` | `knowledgeIndexes.plan` | `client.knowledgeIndexes.plan` | `IndexPlanView` |
| `POST /api/v1/tenants/{tenant_id}/knowledge-indexes` | `create_knowledge_index` | `knowledgeIndexes.create` | `client.knowledgeIndexes.create` | `IndexJobView` |
| `POST /api/v1/tenants/{tenant_id}/knowledge-indexes/{index_id}/activate` | `activate_knowledge_index` | `knowledgeIndexes.activate` | `client.knowledgeIndexes.activate` | `KnowledgeIndexView` |
| `POST /api/v1/tenants/{tenant_id}/knowledge-indexes/{index_id}/cancel` | `cancel_knowledge_index` | `knowledgeIndexes.cancel` | `client.knowledgeIndexes.cancel` | `KnowledgeIndexView` |
| `POST /api/v1/tenants/{tenant_id}/knowledge-indexes/{index_id}/resume` | `resume_knowledge_index` | `knowledgeIndexes.resume` | `client.knowledgeIndexes.resume` | `IndexJobView` |
| `GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/provenance` | `table_provenance` | `dataset.tableProvenance` | `client.datasets.tableProvenance` | `TableProvenance` |
| `GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/snapshots` | `table_snapshots` | `dataset.tableSnapshots` | `client.datasets.tableSnapshots` | `TableSnapshotPage` |
| `GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates` | `table_coordinates` | `dataset.tableCoordinates` | `client.datasets.tableCoordinates` | `TableCoordinateManifest` |
| `POST /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates/cells` | `table_coordinate_cells` | `dataset.tableCoordinateCells` | `client.datasets.tableCoordinateCells` | `TableCoordinateSelection` |
| `GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates/rows` | `table_coordinate_rows` | `dataset.tableCoordinateRows` | `client.datasets.tableCoordinateRows` | `TableRowRangePage` |
| `GET /api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates/columns` | `table_coordinate_columns` | `dataset.tableCoordinateColumns` | `client.datasets.tableCoordinateColumns` | `TableColumnBindingPage` |
| `GET /api/v1/tenants/{tenant_id}/chat/settings` | `organization_chat_settings` | `organizationChat.get` | `client.organizationChat.get` | `OrganizationChatSettings` |
| `PUT /api/v1/tenants/{tenant_id}/chat/settings` | `update_organization_chat_settings` | `organizationChat.update` | `client.organizationChat.update` | `OrganizationChatSettings` |
| `GET /api/v1/tenants/{tenant_id}/knowledge/settings` | `organization_knowledge_settings` | `organizationKnowledge.get` | `client.organizationKnowledge.get` | `OrganizationKnowledgeSettings` |
| `PUT /api/v1/tenants/{tenant_id}/knowledge/settings` | `update_organization_knowledge_settings` | `organizationKnowledge.update` | `client.organizationKnowledge.update` | `OrganizationKnowledgeSettings` |
| `GET /api/v1/profile` | `profile` | `profile.get` | `client.profile.get` | `UserProfile` |
| `PATCH /api/v1/profile` | `update_profile` | `profile.update` | `client.profile.update` | `UserProfile` |
| `GET /api/v1/profile/avatar` | `avatar_download` | `profile.avatarDownload` | `client.profile.avatar` | `BinaryDownload` |
| `POST /api/v1/profile/avatar` | `set_avatar` | `profile.uploadAvatar` | `client.profile.uploadAvatar` | `UserProfile` |
| `DELETE /api/v1/profile/avatar` | `delete_avatar` | `profile.deleteAvatar` | `client.profile.deleteAvatar` | `UserProfile` |
| `GET /api/v1/tenants/{tenant_id}/people` | `people` | `people.list` | `client.people.list` | `Page[Person]` |
| `GET /api/v1/tenants/{tenant_id}/people/{profile_id}/avatar` | `person_avatar` | `people.avatar` | `client.people.avatar` | `BinaryDownload` |
| `POST /api/v1/tenants/{tenant_id}/shares/reviews` | `review_share` | `shares.review` | `client.shares.review` | `ShareReview` |
| `POST /api/v1/tenants/{tenant_id}/shares` | `create_share` | `shares.create` | `client.shares.create` | `Share` |
| `GET /api/v1/tenants/{tenant_id}/shares` | `shares` | `shares.list` | `client.shares.list` | `SharePage` |
| `GET /api/v1/tenants/{tenant_id}/shares/{share_id}` | `share` | `shares.get` | `client.shares.get` | `SharedConversation` |
| `DELETE /api/v1/tenants/{tenant_id}/shares/{share_id}` | `revoke_share` | `shares.revoke` | `client.shares.revoke` | `void` |
| `GET /api/v1/tokens` | `tokens` | `tokens.list` | `client.tokens.list` | `Page[PersonalToken]` |
| `GET /api/v1/tokens/scopes` | `token_scopes` | `tokens.scopes` | `client.tokens.scopes` | `TokenScopeOptions` |
| `POST /api/v1/tokens` | `create_token` | `tokens.create` | `client.tokens.create` | `TokenCreated` |
| `DELETE /api/v1/tokens/{token_id}` | `revoke_token` | `tokens.revoke` | `client.tokens.revoke` | `void` |
| `GET /api/v1/capabilities` | `capabilities` | `capabilities` | `client.platform.capabilities` | `Capabilities` |

## Qualified retained glossary API

These operations use the original structured service behind resource admission. They are separate from the canonical count and require the structured module and its configured native datasource. Pass the canonical tenant and workspace. Updates and deletion require the exact returned `updated_at` string; preserve microseconds and the offset instead of parsing through a date formatter.

| API operation | Python client | TypeScript client | Java client |
| --- | --- | --- | --- |
| `GET /api/v1/structured/glossary` | `glossary_terms` | `structured.glossary.list` | `client.structuredGlossary(tenant,workspace).list` |
| `GET /api/v1/structured/glossary/{term_id}` | `glossary_term` | `structured.glossary.get` | `client.structuredGlossary(tenant,workspace).get` |
| `POST /api/v1/structured/glossary` | `create_glossary_term` | `structured.glossary.create` | `client.structuredGlossary(tenant,workspace).create` |
| `PUT /api/v1/structured/glossary/{term_id}` | `update_glossary_term` | `structured.glossary.update` | `client.structuredGlossary(tenant,workspace).update` |
| `DELETE /api/v1/structured/glossary/{term_id}` | `delete_glossary_term` | `structured.glossary.remove` | `client.structuredGlossary(tenant,workspace).remove` |
| `GET /api/v1/structured/agent/glossary` | `glossary_terms(agent=True)` | `structured.agentGlossary.list` | `client.structuredAgentGlossary(tenant,workspace).list` |
| `GET /api/v1/structured/agent/glossary/{term_id}` | `glossary_term(agent=True)` | `structured.agentGlossary.get` | `client.structuredAgentGlossary(tenant,workspace).get` |
| `POST /api/v1/structured/agent/glossary` | `create_glossary_term(agent=True)` | `structured.agentGlossary.create` | `client.structuredAgentGlossary(tenant,workspace).create` |
| `PUT /api/v1/structured/agent/glossary/{term_id}` | `update_glossary_term(agent=True)` | `structured.agentGlossary.update` | `client.structuredAgentGlossary(tenant,workspace).update` |
| `DELETE /api/v1/structured/agent/glossary/{term_id}` | `delete_glossary_term(agent=True)` | `structured.agentGlossary.remove` | `client.structuredAgentGlossary(tenant,workspace).remove` |

Glossary list totals can be unknown. Honor returned `limit`, `offset` and `has_more`; do not invent a total or slice another page in the client.

## Request behavior

Dataset file append requires a stable Idempotency-Key, accepts one bounded multipart file and returns its canonical file-version and new table identities. Existing snapshots are retained. Native sections commit independently; pending or failed intake blocks dataset query/schema until reconciliation. Exact key/payload replays recheck permissions and return the stored completed receipt without native work. There is no automatic retry, bulk/async intake or public recovery helper. PostgreSQL concurrency and configured-provider acceptance remain separate qualification gates.

Use endpoint-declared filters. Totals and page metadata are present only when the server supplies them. Cursor values are opaque. Closing a stream releases the connection; cancel the durable run separately to stop processing.

Content writes require the caller's current revision. Optional avatar conditionals use `If-None-Match`; stream resumption uses `Last-Event-ID`. These are separate from the `If-Match` precondition on content replacement and reingestion.

Known fields have named DTOs and typed values. Opaque business JSON preserves null, booleans, numbers and exact strings recursively. A successful SDK build or contract test does not qualify a configured model provider or a production deployment.

Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
