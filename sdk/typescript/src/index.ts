// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {createLazyExternalReviewsApi} from './external-review-loader.js';
import {createLazyChatApi} from './chat-loader.js';
import {createLazyFileBatchesApi} from './file-batch-loader.js';
import {createLazyQueryBatchesApi} from './query-batch-loader.js';
export type {QueryBatchesApi,QueryBatchPageFilter} from './query-batches.js';
export type {FileBatchesApi,FileBatchPageFilter} from './file-batches.js';
import {createLazyOrganizationPeopleApi} from './organization-loader.js';
import {createLazyCorporateProfilesApi} from './corporate-profile-loader.js';
export type {CorporateProfilesApi} from './corporate-profiles.js';
export type {OrganizationPeopleApi} from './organization-people.js';
import type {McpConnectionDescriptor} from './generated.js';
import type {McpOAuthClient,McpOAuthClientCredential,McpOAuthClientInput,McpOAuthClientPage,McpOAuthClientPatch,McpOAuthClientReadiness,McpOAuthClientRevision} from './generated.js';
import type {McpOAuthClientFilter} from './types.js';
import type {BrandingValues,OrganizationBranding,OrganizationBrandingInput,BrandingResetInput} from './generated.js';
import type {OrganizationChatSettings,OrganizationChatSettingsInput} from './generated.js';
import type {OrganizationKnowledgeSettings,OrganizationKnowledgeSettingsInput} from './generated.js';
import type {DocumentVersion,DocumentVersionPage,DocumentExtractionPage,DocumentPartPage,DocumentPartContent} from './generated.js';
import type {AnswerAudit,ActivitySummary,ActivityWindow} from './generated.js';
import type {AuthorizedApplication} from './generated.js';
import type {AuthorizedApplicationFilter} from './types.js';
import type {DatasetFileAppendResult} from './generated.js';
import type {TableProvenance,TableSnapshotPage} from './generated.js';
import type {CoordinateCellRequest,TableCoordinateManifest,TableCoordinateSelection,TableRowRangePage,TableColumnBindingPage,KnowledgeIntentInput,KnowledgeIntent,KnowledgeConfirmation,CommittedKnowledge,PendingKnowledgeCommit,KnowledgeItemView,KnowledgeItemPage} from './generated.js';
import type {KoinonTransport,RequestOptions,BinaryDownload} from './transport.js';
import type {AuditFilter,AuditEvent,Capabilities,CatalogEntry,CatalogMove,CatalogFilter,ContextResponse,DatasetSchema,EntryCreate,EntryUpdate,Job,Lineage,MemberInput,Membership,Page,QueryRequest,QueryResponse,SearchRequest,SearchResponse,UploadResponse} from './types.js';
import type {AgentConfiguration,AgentInput,ChatThread,ChatMessage,ChatRun,ChatEventData,Configuration,EvidenceResult,KnowledgeScope,ModelProvider,ProviderInput,RunInput,ValidationResult} from './types.js';
import type {ChatFolder,ThreadCreate,FolderCreate,FolderPatch,ThreadPatch,TitleRequest,TitleSuggestion,FolderFilter,ThreadFilter} from './types.js';
import type {AttachmentView,AttachmentPage,PrivateChunkPage,AttachmentRevision,AttachmentPromotionInput,AttachmentPromotionView} from './generated.js';
import type {ActivityFilter,ToolActivity,AttachmentFilter,AttachmentChunkFilter} from './types.js';
import type {DocumentChunks,ChunkFilter} from './types.js';
import type {MembershipFilter,InvitationFilter,InvitationInput,Invitation,InvitationCreated,InvitationPreview} from './types.js';
import type {UserProfile,ProfileInput,PersonalToken,PersonalTokenInput,CreatedPersonalToken,TokenScopeOptions} from './types.js';
import type {ContentUpdate,ContentPrecondition,MemberUpdate,Person,KnowledgeConnection,KnowledgeConnectionInput,KnowledgeRoles,PageFilter,StatusFilter,SourceUploadInput} from './types.js';
import type {IndexPlanInput,IndexCreateInput,IndexActivateInput,IndexRevisionInput,IndexPlanView,IndexJobView,KnowledgeIndexView,NativeIndexChoice,IndexPage,NativeIndexPage,IdentityProvider,IdentityProviderInput,IdentityProviderPatch,IdentityRevision,IdentityValidation,IdentityActivation,IdentityProviderPage,IdentityGroupPage,IdentityMappingPage,IdentityMappingInput,IdentityMapping,AttachmentCapabilities} from './generated.js';
import type {IndexFilter,IndexScope,IdentityFilter,IdentityGroupFilter,IdentityMappingFilter} from './types.js';
import type {GlossaryPage,GlossaryTermCreate,GlossaryTermUpdate,GlossaryTermRead,CatalogProposal,ProposalConfirmation,ProposalRevision,ExportReviewRequest,ExportReview,ExportCreate,Export,ExportPage,ShareReviewInput,ShareReview,ShareCreate,Share,SharePage,SharedConversation,MessageSelection,EvidenceManifest} from './generated.js';
import type {ExportFilter,ShareFilter,AgentFilter} from './types.js';
export * from './types.js';
export * from './generated.js';
export * from './transport.js';
export type KnowledgeCommitOutcome = CommittedKnowledge | PendingKnowledgeCommit;
const id=encodeURIComponent;
const tenant=(tenantId:string)=>`/tenants/${id(tenantId)}`;
type OrganizationSettingsApi<T,I,F extends boolean>={
 get:F extends true?(tenantId:string,filter?:{workspace_id?:string;project_id?:string},options?:RequestOptions)=>Promise<T>:(tenantId:string,options?:RequestOptions)=>Promise<T>;
 update:(tenantId:string,input:I,options?:RequestOptions)=>Promise<T>;
};
export class KoinonClient {
 get branding(){
  const transport=this.options.transport;
  return {
   defaults:(options:RequestOptions={})=>transport.request<BrandingValues>('GET','/branding/defaults',options),
   get:(tenantId:string,options:RequestOptions={})=>transport.request<OrganizationBranding>('GET',tenant(tenantId)+'/branding',options),
   update:(tenantId:string,input:OrganizationBrandingInput,options:RequestOptions={})=>transport.request<OrganizationBranding>('PUT',tenant(tenantId)+'/branding',{...options,body:input}),
   reset:(tenantId:string,input:BrandingResetInput,options:RequestOptions={})=>transport.request<OrganizationBranding>('POST',tenant(tenantId)+'/branding/reset',{...options,body:input}),
  };
 }
 get organizationKnowledge(){
  return this.organizationSettings<OrganizationKnowledgeSettings,OrganizationKnowledgeSettingsInput,false>('/knowledge/settings',false);
 }
 private organizationSettings<T,I,F extends boolean>(suffix:string,scoped:F):OrganizationSettingsApi<T,I,F>{
  const transport=this.options.transport;
  return {
   get:(tenantId:string,input:RequestOptions|{workspace_id?:string;project_id?:string}={},options:RequestOptions={})=>transport.request<T>('GET',tenant(tenantId)+suffix,scoped?{...options,query:{...input as {workspace_id?:string;project_id?:string}}}:input as RequestOptions),
   update:(tenantId:string,input:I,options:RequestOptions={})=>transport.request<T>('PUT',tenant(tenantId)+suffix,{...options,body:input}),
  } as OrganizationSettingsApi<T,I,F>;
 }
 readonly mcp;
 readonly mcpOAuthClients;
 readonly externalReviews;
 readonly externalFileReviews;
 readonly knowledgeIntents;
 readonly knowledgeItems;
 readonly catalog;
 readonly sources;
 readonly dataset;
 readonly documents;
 readonly jobs;
 readonly members;
 readonly invitations;
 readonly audit;
 readonly activity;
 readonly configuration;
 readonly providers;
 readonly agents;
 readonly chat;
 readonly profile;
 readonly tokens;
 readonly authorizedApplications;
 readonly organizationChat;
 readonly organizationPeople;
 readonly corporateProfiles;
 readonly fileBatches;
 readonly queryBatches;
 readonly people;
 readonly knowledgeConnections;
 readonly knowledgeIndexes;
 readonly identity;
 readonly exports;
 readonly shares;
 readonly evidence;
 readonly structured;
 constructor(private readonly options:{transport:KoinonTransport}){
  const transport=options.transport;
  const match=(value:string)=>{if(!value||/["\r\n\0]/.test(value))throw new Error('Supply the unquoted current digest or snapshot ID');return '"'+value+'"';};
  const documentRevisionHeaders=(input:{expected_source_version_id?:string|null;expected_extraction_id?:string|null}):Record<string,string>=>{const version=input.expected_source_version_id,extraction=input.expected_extraction_id;if((version==null)!==(extraction==null))throw new Error('Supply the exact source version and extraction together');if(version==null||extraction==null)return {};const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;if(!uuid.test(version)||!uuid.test(extraction))throw new Error('Document revision identities must be UUID strings');return {'X-Koinon-Source-Version':version,'X-Koinon-Extraction':extraction};};
  const multipart=(file:Blob,filename?:string)=>{const body=new FormData();const named='name' in file&&typeof file.name==='string'?file.name:undefined;const selected=filename??named;if(!selected)throw new Error('A replacement filename with its supported extension is required');body.set('file',file,selected);return body;};
  const glossary=(agent:boolean)=>{
   const path='/structured/'+(agent?'agent/':'')+'glossary';
   const headers=(tenantId:string,workspaceId:string,options:RequestOptions,revision?:string)=>({...options.headers,'X-Tenant-ID':tenantId,'X-Workspace-ID':workspaceId,...(revision!==undefined?{'If-Match':match(revision)}:{})});
   return {
    list:(tenantId:string,workspaceId:string,options:RequestOptions&{query?:{limit?:number;offset?:number}}={})=>transport.request<GlossaryPage>('GET',path,{...options,headers:headers(tenantId,workspaceId,options)}),
    get:(tenantId:string,workspaceId:string,termId:string,options:RequestOptions={})=>transport.request<GlossaryTermRead>('GET',path+'/'+id(termId),{...options,headers:headers(tenantId,workspaceId,options)}),
    create:(tenantId:string,workspaceId:string,input:GlossaryTermCreate,options:RequestOptions={})=>transport.request<GlossaryTermRead>('POST',path,{...options,body:input,headers:headers(tenantId,workspaceId,options)}),
    update:(tenantId:string,workspaceId:string,termId:string,input:GlossaryTermUpdate,expectedUpdatedAt:string,options:RequestOptions={})=>transport.request<GlossaryTermRead>('PUT',path+'/'+id(termId),{...options,body:input,headers:headers(tenantId,workspaceId,options,expectedUpdatedAt)}),
    remove:(tenantId:string,workspaceId:string,termId:string,expectedUpdatedAt:string,options:RequestOptions={})=>transport.request<void>('DELETE',path+'/'+id(termId),{...options,headers:headers(tenantId,workspaceId,options,expectedUpdatedAt)}),
   };
  };
  this.mcp={
   connection:(options:RequestOptions={})=>transport.request<McpConnectionDescriptor>('GET','/mcp/connection',options),
   organizationConnection:(tenantId:string,options:RequestOptions={})=>transport.request<McpConnectionDescriptor>('GET',tenant(tenantId)+'/mcp/connection',options),
  };
  this.mcpOAuthClients={
   readiness:(tenantId:string,options:RequestOptions={})=>transport.request<McpOAuthClientReadiness>('GET',tenant(tenantId)+'/mcp/oauth-clients/readiness',options),
   list:(tenantId:string,options:RequestOptions&{query?:McpOAuthClientFilter}={})=>transport.request<McpOAuthClientPage>('GET',tenant(tenantId)+'/mcp/oauth-clients',options),
   create:(tenantId:string,input:McpOAuthClientInput,options:RequestOptions={})=>transport.request<McpOAuthClientCredential>('POST',tenant(tenantId)+'/mcp/oauth-clients',{...options,body:input}),
   get:(tenantId:string,clientId:string,options:RequestOptions={})=>transport.request<McpOAuthClient>('GET',tenant(tenantId)+'/mcp/oauth-clients/'+id(clientId),options),
   update:(tenantId:string,clientId:string,input:McpOAuthClientPatch,options:RequestOptions={})=>transport.request<McpOAuthClient>('PATCH',tenant(tenantId)+'/mcp/oauth-clients/'+id(clientId),{...options,body:input}),
   rotateSecret:(tenantId:string,clientId:string,input:McpOAuthClientRevision,options:RequestOptions={})=>transport.request<McpOAuthClientCredential>('POST',tenant(tenantId)+'/mcp/oauth-clients/'+id(clientId)+'/rotate-secret',{...options,body:input}),
  };
  const external=createLazyExternalReviewsApi(transport);
  this.externalFileReviews=external.externalFileReviews;
  this.externalReviews=external.externalReviews;
  this.organizationChat=this.organizationSettings<OrganizationChatSettings,OrganizationChatSettingsInput,true>('/chat/settings',true);
  this.structured={glossary:glossary(false),agentGlossary:glossary(true)};
  this.exports={
   review:(tenantId:string,input:ExportReviewRequest,options:RequestOptions={})=>transport.request<ExportReview>('POST',`${tenant(tenantId)}/exports/reviews`,{...options,body:input}),
   create:(tenantId:string,input:ExportCreate,options:RequestOptions={})=>transport.request<Export>('POST',`${tenant(tenantId)}/exports`,{...options,body:input}),
   list:(tenantId:string,options:RequestOptions&{query?:ExportFilter}={})=>transport.request<ExportPage>('GET',`${tenant(tenantId)}/exports`,options),
   get:(tenantId:string,exportId:string,options:RequestOptions={})=>transport.request<Export>('GET',`${tenant(tenantId)}/exports/${id(exportId)}`,options),
   download:(tenantId:string,exportId:string,options:RequestOptions={})=>transport.request<BinaryDownload>('GET',`${tenant(tenantId)}/exports/${id(exportId)}/download`,{...options,responseType:'download'}),
   cancel:(tenantId:string,exportId:string,options:RequestOptions={})=>transport.request<void>('DELETE',`${tenant(tenantId)}/exports/${id(exportId)}`,options),
  };
  this.shares={
   review:(tenantId:string,input:ShareReviewInput,options:RequestOptions={})=>transport.request<ShareReview>('POST',`${tenant(tenantId)}/shares/reviews`,{...options,body:input}),
   create:(tenantId:string,input:ShareCreate,options:RequestOptions={})=>transport.request<Share>('POST',`${tenant(tenantId)}/shares`,{...options,body:input}),
   list:(tenantId:string,options:RequestOptions&{query?:ShareFilter}={})=>transport.request<SharePage>('GET',`${tenant(tenantId)}/shares`,options),
   get:(tenantId:string,shareId:string,options:RequestOptions={})=>transport.request<SharedConversation>('GET',`${tenant(tenantId)}/shares/${id(shareId)}`,options),
   revoke:(tenantId:string,shareId:string,options:RequestOptions={})=>transport.request<void>('DELETE',`${tenant(tenantId)}/shares/${id(shareId)}`,options),
  };
  this.evidence={
   conversation:(tenantId:string,input:MessageSelection,options:RequestOptions={})=>transport.request<EvidenceManifest>('POST',`${tenant(tenantId)}/evidence/conversations`,{...options,body:input}),
  };
  this.knowledgeIndexes={
   list:(tenantId:string,filter:IndexFilter,options:RequestOptions={})=>transport.request<IndexPage>('GET',`${tenant(tenantId)}/knowledge-indexes`,{...options,query:{...filter}}),
   choices:(tenantId:string,filter:IndexFilter,options:RequestOptions={})=>transport.request<NativeIndexPage>('GET',`${tenant(tenantId)}/knowledge-index-choices`,{...options,query:{...filter}}),
   choice:(tenantId:string,indexId:string,filter:IndexScope,options:RequestOptions={})=>transport.request<NativeIndexChoice>('GET',`${tenant(tenantId)}/knowledge-index-choices/${id(indexId)}`,{...options,query:{...filter}}),
   get:(tenantId:string,indexId:string,options:RequestOptions={})=>transport.request<KnowledgeIndexView>('GET',`${tenant(tenantId)}/knowledge-indexes/${id(indexId)}`,options),
   plan:(tenantId:string,input:IndexPlanInput,options:RequestOptions={})=>transport.request<IndexPlanView>('POST',`${tenant(tenantId)}/knowledge-indexes/plan`,{...options,body:input}),
   create:(tenantId:string,input:IndexCreateInput,idempotencyKey:string,options:RequestOptions={})=>transport.request<IndexJobView>('POST',`${tenant(tenantId)}/knowledge-indexes`,{...options,body:input,headers:{...options.headers,'Idempotency-Key':idempotencyKey}}),
   activate:(tenantId:string,indexId:string,input:IndexActivateInput,options:RequestOptions={})=>transport.request<KnowledgeIndexView>('POST',`${tenant(tenantId)}/knowledge-indexes/${id(indexId)}/activate`,{...options,body:input}),
   cancel:(tenantId:string,indexId:string,input:IndexRevisionInput,options:RequestOptions={})=>transport.request<KnowledgeIndexView>('POST',`${tenant(tenantId)}/knowledge-indexes/${id(indexId)}/cancel`,{...options,body:input}),
   resume:(tenantId:string,indexId:string,input:IndexRevisionInput,idempotencyKey:string,options:RequestOptions={})=>transport.request<IndexJobView>('POST',`${tenant(tenantId)}/knowledge-indexes/${id(indexId)}/resume`,{...options,body:input,headers:{...options.headers,'Idempotency-Key':idempotencyKey}}),
  };
  this.identity={
   list:(tenantId:string,options:RequestOptions&{query?:IdentityFilter}={})=>transport.request<IdentityProviderPage>('GET',`${tenant(tenantId)}/identity/providers`,options),
   create:(tenantId:string,input:IdentityProviderInput,options:RequestOptions={})=>transport.request<IdentityProvider>('POST',`${tenant(tenantId)}/identity/providers`,{...options,body:input}),
   get:(tenantId:string,providerId:string,options:RequestOptions={})=>transport.request<IdentityProvider>('GET',`${tenant(tenantId)}/identity/providers/${id(providerId)}`,options),
   update:(tenantId:string,providerId:string,input:IdentityProviderPatch,options:RequestOptions={})=>transport.request<IdentityProvider>('PATCH',`${tenant(tenantId)}/identity/providers/${id(providerId)}`,{...options,body:input}),
   test:(tenantId:string,providerId:string,input:IdentityRevision,options:RequestOptions={})=>transport.request<IdentityValidation>('POST',`${tenant(tenantId)}/identity/providers/${id(providerId)}/test`,{...options,body:input}),
   testStatus:(tenantId:string,providerId:string,validationId:string,options:RequestOptions={})=>transport.request<IdentityValidation>('GET',`${tenant(tenantId)}/identity/providers/${id(providerId)}/tests/${id(validationId)}`,options),
   groups:(tenantId:string,providerId:string,options:RequestOptions&{query?:IdentityGroupFilter}={})=>transport.request<IdentityGroupPage>('GET',`${tenant(tenantId)}/identity/providers/${id(providerId)}/groups`,options),
   mappings:(tenantId:string,providerId:string,options:RequestOptions&{query?:IdentityMappingFilter}={})=>transport.request<IdentityMappingPage>('GET',`${tenant(tenantId)}/identity/providers/${id(providerId)}/mappings`,options),
   createMapping:(tenantId:string,providerId:string,input:IdentityMappingInput,options:RequestOptions={})=>transport.request<IdentityMapping>('POST',`${tenant(tenantId)}/identity/providers/${id(providerId)}/mappings`,{...options,body:input}),
   updateMapping:(tenantId:string,providerId:string,mappingId:string,input:IdentityMappingInput,options:RequestOptions={})=>transport.request<IdentityMapping>('PATCH',`${tenant(tenantId)}/identity/providers/${id(providerId)}/mappings/${id(mappingId)}`,{...options,body:input}),
   removeMapping:(tenantId:string,providerId:string,mappingId:string,expectedRevision:number,options:RequestOptions={})=>transport.request<void>('DELETE',`${tenant(tenantId)}/identity/providers/${id(providerId)}/mappings/${id(mappingId)}`,{...options,query:{expected_revision:expectedRevision}}),
   activate:(tenantId:string,providerId:string,input:IdentityActivation,options:RequestOptions={})=>transport.request<IdentityProvider>('POST',`${tenant(tenantId)}/identity/providers/${id(providerId)}/activate`,{...options,body:input}),
   disable:(tenantId:string,providerId:string,input:IdentityRevision,options:RequestOptions={})=>transport.request<IdentityProvider>('POST',`${tenant(tenantId)}/identity/providers/${id(providerId)}/disable`,{...options,body:input}),
  };
  this.organizationPeople=createLazyOrganizationPeopleApi(transport);
  this.corporateProfiles=createLazyCorporateProfilesApi(transport);
  this.fileBatches=createLazyFileBatchesApi(transport);
  this.queryBatches=createLazyQueryBatchesApi(transport);
  this.people={
   list:(tenantId:string,filter:{workspace_id?:string;q?:string;limit?:number;after?:string|undefined}={},options:RequestOptions={})=>transport.request<Page<Person>>('GET',`${tenant(tenantId)}/people`,{...options,query:{...filter}}),
   avatar:(tenantId:string,profileId:string,workspaceId?:string,options:RequestOptions={})=>transport.request<BinaryDownload>('GET',`${tenant(tenantId)}/people/${id(profileId)}/avatar`,{...options,query:{workspace_id:workspaceId},responseType:'download'}),
  };
  this.knowledgeConnections={
   get:(tenantId:string,connectionId:string,options:RequestOptions={})=>transport.request<KnowledgeConnection>('GET',`${tenant(tenantId)}/knowledge-connections/${id(connectionId)}`,options),
   roles:(tenantId:string,workspaceId?:string,options:RequestOptions={})=>transport.request<KnowledgeRoles>('GET',`${tenant(tenantId)}/knowledge-roles`,{...options,query:{workspace_id:workspaceId}}),
   list:(tenantId:string,workspaceId?:string,options:RequestOptions={})=>transport.request<Page<KnowledgeConnection>>('GET',`${tenant(tenantId)}/knowledge-connections`,{...options,query:{workspace_id:workspaceId}}),
   create:(tenantId:string,input:KnowledgeConnectionInput,options:RequestOptions={})=>transport.request<KnowledgeConnection>('POST',`${tenant(tenantId)}/knowledge-connections`,{...options,body:input}),
   update:(tenantId:string,connectionId:string,input:KnowledgeConnectionInput,options:RequestOptions={})=>transport.request<KnowledgeConnection>('PUT',`${tenant(tenantId)}/knowledge-connections/${id(connectionId)}`,{...options,body:input}),
   remove:(tenantId:string,connectionId:string,expectedRevision:number,options:RequestOptions={})=>transport.request<{deleted:boolean}>('DELETE',`${tenant(tenantId)}/knowledge-connections/${id(connectionId)}`,{...options,query:{expected_revision:expectedRevision}}),
  };
  this.profile={
   get:(options:RequestOptions={})=>transport.request<UserProfile>('GET','/profile',options),
   update:(input:ProfileInput,options:RequestOptions={})=>transport.request<UserProfile>('PATCH','/profile',{...options,body:input}),
   avatarDownload:(options:RequestOptions={})=>transport.request<BinaryDownload>('GET','/profile/avatar',{...options,responseType:'download'}),
   avatar:(options:RequestOptions={})=>transport.request<Blob>('GET','/profile/avatar',{...options,responseType:'blob'}),
   uploadAvatar:(file:Blob,options:RequestOptions={})=>transport.request<UserProfile>('POST','/profile/avatar',{...options,body:file,headers:{...options.headers,'Content-Type':file.type}}),
   deleteAvatar:(options:RequestOptions={})=>transport.request<UserProfile>('DELETE','/profile/avatar',options),
  };
  this.authorizedApplications={
   list:(options:RequestOptions&{query?:AuthorizedApplicationFilter}={})=>transport.request<Page<AuthorizedApplication>>('GET','/authorized-applications',options),
   get:(applicationId:string,options:RequestOptions={})=>transport.request<AuthorizedApplication>('GET',`/authorized-applications/${id(applicationId)}`,options),
   revoke:(applicationId:string,options:RequestOptions={})=>transport.request<void>('DELETE',`/authorized-applications/${id(applicationId)}`,options),
  };
  this.tokens={
   list:(options:RequestOptions&{query?:StatusFilter}={})=>transport.request<Page<PersonalToken>>('GET','/tokens',options),
   create:(input:PersonalTokenInput,options:RequestOptions={})=>transport.request<CreatedPersonalToken>('POST','/tokens',{...options,body:input}),
   revoke:(tokenId:string,options:RequestOptions={})=>transport.request<void>('DELETE',`/tokens/${id(tokenId)}`,options),
   scopes:(tenantId:string,workspaceId?:string,options:RequestOptions={})=>transport.request<TokenScopeOptions>('GET','/tokens/scopes',{...options,query:{tenant_id:tenantId,workspace_id:workspaceId}}),
  };
  this.configuration={get:(tenantId:string,options:RequestOptions={})=>transport.request<Configuration>('GET',`${tenant(tenantId)}/configuration`,options)};
  this.providers={
   create:(tenantId:string,input:ProviderInput,options:RequestOptions={})=>transport.request<ModelProvider>('POST',`${tenant(tenantId)}/providers`,{...options,body:input}),
   update:(tenantId:string,providerId:string,input:ProviderInput,options:RequestOptions={})=>transport.request<ModelProvider>('PUT',`${tenant(tenantId)}/providers/${id(providerId)}`,{...options,body:input}),
   validate:(tenantId:string,providerId:string,options:RequestOptions={})=>transport.request<ValidationResult>('POST',`${tenant(tenantId)}/providers/${id(providerId)}/validate`,options),
  };
  this.agents={
   list:(tenantId:string,options:RequestOptions&{query?:AgentFilter}={})=>transport.request<Page<AgentConfiguration>>('GET',`${tenant(tenantId)}/agents`,options),
   create:(tenantId:string,input:AgentInput,options:RequestOptions={})=>transport.request<AgentConfiguration>('POST',`${tenant(tenantId)}/agents`,{...options,body:input}),
   update:(tenantId:string,agentId:string,input:AgentInput,options:RequestOptions={})=>transport.request<AgentConfiguration>('PATCH',`${tenant(tenantId)}/agents/${id(agentId)}`,{...options,body:input}),
   validate:(tenantId:string,agentId:string,options:RequestOptions={})=>transport.request<AgentConfiguration>('POST',`${tenant(tenantId)}/agents/${id(agentId)}/validate`,options),
  };
  this.chat=createLazyChatApi(transport);
  this.catalog={
   list:(tenantId:string,filter:CatalogFilter={},options:RequestOptions={})=>transport.request<Page<CatalogEntry>>('GET',`${tenant(tenantId)}/catalog`,{...options,query:{...filter}}),
   create:(tenantId:string,entry:EntryCreate,options:RequestOptions={})=>transport.request<CatalogEntry>('POST',`${tenant(tenantId)}/catalog`,{...options,body:entry}),
   get:(tenantId:string,entryId:string,options:RequestOptions={})=>transport.request<CatalogEntry>('GET',`${tenant(tenantId)}/catalog/${id(entryId)}`,options),
   update:(tenantId:string,entryId:string,entry:EntryUpdate,options:RequestOptions={})=>transport.request<CatalogEntry>('PATCH',`${tenant(tenantId)}/catalog/${id(entryId)}`,{...options,body:entry}),
   restore:(tenantId:string,entryId:string,options:RequestOptions={})=>transport.request<CatalogEntry>('POST',`${tenant(tenantId)}/catalog/${id(entryId)}/restore`,options),
   delete:(tenantId:string,entryId:string,options:RequestOptions={})=>transport.request<void>('DELETE',`${tenant(tenantId)}/catalog/${id(entryId)}`,options),
   move:(tenantId:string,entryId:string,input:CatalogMove,options:RequestOptions={})=>transport.request<CatalogEntry>('POST',`${tenant(tenantId)}/catalog/${id(entryId)}/move`,{...options,body:input}),
   archive:(tenantId:string,entryId:string,options:RequestOptions={})=>transport.request<CatalogEntry>('POST',`${tenant(tenantId)}/catalog/${id(entryId)}/archive`,options),
  };
  this.sources={uploadFile:(tenantId:string,input:SourceUploadInput,options:RequestOptions={})=>{const body=multipart(input.file,input.filename);for(const key of ['workspace_id','project_id','parent_id','mode'] as const)body.set(key,input[key]);return transport.request<UploadResponse>('POST',`${tenant(tenantId)}/sources/upload`,{...options,body});},upload:(tenantId:string,form:FormData,options:RequestOptions={})=>transport.request<UploadResponse>('POST',`${tenant(tenantId)}/sources/upload`,{...options,body:form})};
  const versionPath=(tenantId:string,documentId:string,versionId?:string)=>`${tenant(tenantId)}/documents/${id(documentId)}/versions${versionId===undefined?'':'/'+id(versionId)}`;
  this.documents={
   versions:(tenantId:string,documentId:string,filter:{page?:number;page_size?:number}={},options:RequestOptions={})=>transport.request<DocumentVersionPage>('GET',versionPath(tenantId,documentId),{...options,query:{...filter}}),
   version:(tenantId:string,documentId:string,versionId:string,options:RequestOptions={})=>transport.request<DocumentVersion>('GET',versionPath(tenantId,documentId,versionId),options),
   extractions:(tenantId:string,documentId:string,versionId:string,filter:{page?:number;page_size?:number}={},options:RequestOptions={})=>transport.request<DocumentExtractionPage>('GET',versionPath(tenantId,documentId,versionId)+'/extractions',{...options,query:{...filter}}),
   parts:(tenantId:string,documentId:string,versionId:string,extractionId:string,filter:{page?:number;page_size?:number;kind?:'artifact'|'section'|'chunk'|'page'}={},options:RequestOptions={})=>transport.request<DocumentPartPage>('GET',versionPath(tenantId,documentId,versionId)+'/extractions/'+id(extractionId)+'/parts',{...options,query:{...filter}}),
   part:(tenantId:string,documentId:string,versionId:string,extractionId:string,partId:string,options:RequestOptions={})=>transport.request<DocumentPartContent>('GET',versionPath(tenantId,documentId,versionId)+'/extractions/'+id(extractionId)+'/parts/'+id(partId),options),
   versionOriginal:(tenantId:string,documentId:string,versionId:string,options:RequestOptions={})=>transport.request<BinaryDownload>('GET',versionPath(tenantId,documentId,versionId)+'/original',{...options,responseType:'download'}),
   download:(tenantId:string,documentId:string,options:RequestOptions={})=>transport.request<BinaryDownload>('GET',`${tenant(tenantId)}/documents/${id(documentId)}/original`,{...options,responseType:'download'}),
   replace:(tenantId:string,documentId:string,file:Blob,input:ContentPrecondition,options:RequestOptions={})=>{const body=multipart(file,input.filename);body.set('acknowledge_chunk_invalidation',String(input.acknowledge_chunk_invalidation??false));return transport.request<ContentUpdate>('POST',`${tenant(tenantId)}/documents/${id(documentId)}/content`,{...options,body,headers:{...options.headers,...documentRevisionHeaders(input),'If-Match':match(input.expected_sha256)}});},
   reingest:(tenantId:string,documentId:string,input:ContentPrecondition,options:RequestOptions={})=>transport.request<ContentUpdate>('POST',`${tenant(tenantId)}/documents/${id(documentId)}/reingest`,{...options,body:{acknowledge_chunk_invalidation:input.acknowledge_chunk_invalidation??false},headers:{...options.headers,...documentRevisionHeaders(input),'If-Match':match(input.expected_sha256)}}),
   chunks:(tenantId:string,documentId:string,filter:ChunkFilter={},options:RequestOptions={})=>transport.request<DocumentChunks>('GET',`${tenant(tenantId)}/documents/${id(documentId)}/chunks`,{...options,query:{...filter}}),
   original:(tenantId:string,documentId:string,options:RequestOptions={})=>transport.request<Blob>('GET',`${tenant(tenantId)}/documents/${id(documentId)}/original`,{...options,responseType:'blob'}),
  };
  this.knowledgeIntents={
   preview:(tenantId:string,input:KnowledgeIntentInput,options:RequestOptions={})=>transport.request<KnowledgeIntent>('POST',`${tenant(tenantId)}/knowledge-intents`,{...options,body:input}),
   get:(tenantId:string,intentId:string,options:RequestOptions={})=>transport.request<KnowledgeIntent>('GET',`${tenant(tenantId)}/knowledge-intents/${id(intentId)}`,options),
   confirm:(tenantId:string,intentId:string,input:KnowledgeConfirmation,key:string,options:RequestOptions={})=>transport.request<KnowledgeCommitOutcome>('POST',`${tenant(tenantId)}/knowledge-intents/${id(intentId)}/confirm`,{...options,body:input,headers:{...options.headers,'Idempotency-Key':key}}),
   cancel:(tenantId:string,intentId:string,expectedRevision:number,options:RequestOptions={})=>transport.request<KnowledgeIntent>('POST',`${tenant(tenantId)}/knowledge-intents/${id(intentId)}/cancel`,{...options,body:{expected_revision:expectedRevision}}),
  };
  this.knowledgeItems={
   list:(tenantId:string,filter:{workspace_id?:string;project_id?:string;destination_id?:string;q?:string;page?:number;page_size?:number}={},options:RequestOptions={})=>transport.request<KnowledgeItemPage>('GET',`${tenant(tenantId)}/knowledge-items`,{...options,query:{...filter}}),
   get:(tenantId:string,itemId:string,options:RequestOptions={})=>transport.request<KnowledgeItemView>('GET',`${tenant(tenantId)}/knowledge-items/${id(itemId)}`,options),
   version:(tenantId:string,itemId:string,version:number,options:RequestOptions={})=>transport.request<KnowledgeItemView>('GET',`${tenant(tenantId)}/knowledge-items/${id(itemId)}/versions/${version}`,options),
  };
  this.dataset={
   appendFile:(tenantId:string,datasetId:string,file:Blob,idempotencyKey:string,options:RequestOptions&{filename?:string}={})=>transport.request<DatasetFileAppendResult>('POST',`${tenant(tenantId)}/datasets/${id(datasetId)}/files`,{...options,body:multipart(file,options.filename),headers:{...options.headers,'Idempotency-Key':idempotencyKey}}),
   tableCoordinates:(tenantId:string,datasetId:string,tableId:string,snapshotId:string,options:RequestOptions={})=>transport.request<TableCoordinateManifest>('GET',`${tenant(tenantId)}/datasets/${id(datasetId)}/tables/${id(tableId)}/coordinates`,{...options,query:{snapshot_id:snapshotId}}),
   tableCoordinateCells:(tenantId:string,datasetId:string,tableId:string,input:CoordinateCellRequest,options:RequestOptions={})=>transport.request<TableCoordinateSelection>('POST',`${tenant(tenantId)}/datasets/${id(datasetId)}/tables/${id(tableId)}/coordinates/cells`,{...options,body:input}),
   tableCoordinateRows:(tenantId:string,datasetId:string,tableId:string,snapshotId:string,options:RequestOptions&{query?:{page?:number;page_size?:number}}={})=>transport.request<TableRowRangePage>('GET',`${tenant(tenantId)}/datasets/${id(datasetId)}/tables/${id(tableId)}/coordinates/rows`,{...options,query:{...options.query,snapshot_id:snapshotId}}),
   tableCoordinateColumns:(tenantId:string,datasetId:string,tableId:string,snapshotId:string,options:RequestOptions&{query?:{page?:number;page_size?:number}}={})=>transport.request<TableColumnBindingPage>('GET',`${tenant(tenantId)}/datasets/${id(datasetId)}/tables/${id(tableId)}/coordinates/columns`,{...options,query:{...options.query,snapshot_id:snapshotId}}),
   tableProvenance:(tenantId:string,datasetId:string,tableId:string,snapshotId:string,options:RequestOptions={})=>transport.request<TableProvenance>('GET',`${tenant(tenantId)}/datasets/${id(datasetId)}/tables/${id(tableId)}/provenance`,{...options,query:{snapshot_id:snapshotId}}),
   tableSnapshots:(tenantId:string,datasetId:string,tableId:string,options:RequestOptions&{query?:{page?:number;page_size?:number}}={})=>transport.request<TableSnapshotPage>('GET',`${tenant(tenantId)}/datasets/${id(datasetId)}/tables/${id(tableId)}/snapshots`,options),
   replaceTable:(tenantId:string,datasetId:string,tableId:string,file:Blob,expectedSnapshotId:string,options:RequestOptions&{filename?:string}={})=>{const body=multipart(file,options.filename);return transport.request<ContentUpdate>('POST',`${tenant(tenantId)}/datasets/${id(datasetId)}/tables/${id(tableId)}/content`,{...options,body,headers:{...options.headers,'If-Match':match(expectedSnapshotId)}});},
   reingestTable:(tenantId:string,datasetId:string,tableId:string,expectedSnapshotId:string,options:RequestOptions={})=>transport.request<ContentUpdate>('POST',`${tenant(tenantId)}/datasets/${id(datasetId)}/tables/${id(tableId)}/reingest`,{...options,body:{},headers:{...options.headers,'If-Match':match(expectedSnapshotId)}}),
   schema:(tenantId:string,datasetId:string,options:RequestOptions={})=>transport.request<DatasetSchema>('GET',`${tenant(tenantId)}/datasets/${id(datasetId)}/schema`,options)};
  this.jobs={
   list:(tenantId:string,options:RequestOptions={})=>transport.request<Page<Job>>('GET',`${tenant(tenantId)}/jobs`,options),
   get:(tenantId:string,jobId:string,options:RequestOptions={})=>transport.request<Job>('GET',`${tenant(tenantId)}/jobs/${id(jobId)}`,options),
   cancel:(tenantId:string,jobId:string,options:RequestOptions={})=>transport.request<Job>('POST',`${tenant(tenantId)}/jobs/${id(jobId)}/cancel`,options),
  };
  this.members={
   list:(tenantId:string,options:RequestOptions&{query?:MembershipFilter}={})=>transport.request<Page<Membership>>('GET',`${tenant(tenantId)}/members`,options),
   add:(tenantId:string,member:MemberInput,options:RequestOptions={})=>transport.request<Membership>('POST',`${tenant(tenantId)}/members`,{...options,body:member}),
   update:(tenantId:string,memberId:string,member:MemberUpdate,options:RequestOptions={})=>transport.request<Membership>('PATCH',`${tenant(tenantId)}/members/${id(memberId)}`,{...options,body:member}),
   remove:(tenantId:string,memberId:string,options:RequestOptions={})=>transport.request<void>('DELETE',`${tenant(tenantId)}/members/${id(memberId)}`,options),
  };
  this.invitations={
   list:(tenantId:string,options:RequestOptions&{query?:InvitationFilter}={})=>transport.request<Page<Invitation>>('GET',`${tenant(tenantId)}/invitations`,options),
   create:(tenantId:string,input:InvitationInput,options:RequestOptions={})=>transport.request<InvitationCreated>('POST',`${tenant(tenantId)}/invitations`,{...options,body:input}),
   revoke:(tenantId:string,invitationId:string,options:RequestOptions={})=>transport.request<void>('DELETE',`${tenant(tenantId)}/invitations/${id(invitationId)}`,options),
   inspect:(token:string,options:RequestOptions={})=>transport.request<InvitationPreview>('POST','/invitations/inspect',{...options,body:{token}}),
   redeem:(token:string,options:RequestOptions={})=>transport.request<Membership>('POST','/invitations/redeem',{...options,body:{token}}),
  };
  this.activity={
   personal:(tenantId:string,input:ActivityWindow,options:RequestOptions={})=>transport.request<ActivitySummary>('POST',`${tenant(tenantId)}/activity/personal`,{...options,body:input}),
   administrative:(tenantId:string,input:ActivityWindow,options:RequestOptions={})=>transport.request<ActivitySummary>('POST',`${tenant(tenantId)}/activity/administration`,{...options,body:input}),
  };
  this.audit={list:(tenantId:string,options:RequestOptions&{query?:AuditFilter}={})=>transport.request<Page<AuditEvent>>('GET',`${tenant(tenantId)}/audit`,options)};
 }
 context(options:RequestOptions={}){return this.options.transport.request<ContextResponse>('GET','/context',options);}
 capabilities(options:RequestOptions={}){return this.options.transport.request<Capabilities>('GET','/capabilities',options);}
 search(tenantId:string,request:SearchRequest,options:RequestOptions={}){return this.options.transport.request<SearchResponse>('POST',`${tenant(tenantId)}/search`,{...options,body:request});}
 query(tenantId:string,request:QueryRequest,options:RequestOptions={}){return this.options.transport.request<QueryResponse>('POST',`${tenant(tenantId)}/query`,{...options,body:request});}
 lineage(tenantId:string,assetId?:string,options:RequestOptions={}){return this.options.transport.request<Lineage>('GET',`${tenant(tenantId)}/lineage`,{...options,query:assetId?{asset_id:assetId}:{}});}
}
export {exactDecimal,exactInteger} from './exact.js';
export {offsetPages,cursorPages} from './pagination.js';
export type * from './communications-models.js';
