// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {AttachmentCapabilities,AttachmentView,AttachmentPage,PrivateChunkPage,AttachmentRevision,AttachmentPromotionInput,AttachmentPromotionView,CatalogProposal,ProposalConfirmation,ProposalRevision,AnswerAudit} from './generated.js';
import type {ActivityFilter,ToolActivity,AttachmentFilter,AttachmentChunkFilter,ChatThread,ThreadPatch,TitleRequest,TitleSuggestion,ChatFolder,FolderFilter,FolderCreate,FolderPatch,ThreadFilter,ThreadCreate,Page,ChatMessage,RunInput,ChatRun,ChatEventData,EvidenceResult} from './types.js';
import type {KoinonTransport,RequestOptions,BinaryDownload} from './transport.js';
const id=encodeURIComponent;
const tenant=(value:string)=>`/tenants/${id(value)}`;
export function createChatApi(transport:KoinonTransport){
  const multipart=(file:Blob,filename?:string)=>{const body=new FormData();const named='name' in file&&typeof file.name==='string'?file.name:undefined;const selected=filename??named;if(!selected)throw new Error('A replacement filename with its supported extension is required');body.set('file',file,selected);return body;};
 return {
   proposals:{
    get:(tenantId:string,runId:string,proposalId:string,options:RequestOptions={})=>transport.request<CatalogProposal>('GET',`${tenant(tenantId)}/chat/runs/${id(runId)}/proposals/${id(proposalId)}`,options),
    confirm:(tenantId:string,runId:string,proposalId:string,input:ProposalConfirmation,options:RequestOptions={})=>transport.request<CatalogProposal>('POST',`${tenant(tenantId)}/chat/runs/${id(runId)}/proposals/${id(proposalId)}/confirm`,{...options,body:input}),
    cancel:(tenantId:string,runId:string,proposalId:string,input:ProposalRevision,options:RequestOptions={})=>transport.request<CatalogProposal>('POST',`${tenant(tenantId)}/chat/runs/${id(runId)}/proposals/${id(proposalId)}/cancel`,{...options,body:input}),
   },
   audit:(tenantId:string,runId:string,options:RequestOptions={})=>transport.request<AnswerAudit>('GET',`${tenant(tenantId)}/chat/runs/${id(runId)}/audit`,options),
   activities:(tenantId:string,runId:string,options:RequestOptions&{query?:ActivityFilter}={})=>transport.request<Page<ToolActivity>>('GET',`${tenant(tenantId)}/chat/runs/${id(runId)}/activity`,options),
   attachments:{
    promote:(tenantId:string,threadId:string,attachmentId:string,input:AttachmentPromotionInput,idempotencyKey:string,options:RequestOptions={})=>transport.request<AttachmentPromotionView>('POST',`${tenant(tenantId)}/chat/threads/${id(threadId)}/attachments/${id(attachmentId)}/knowledge`,{...options,body:input,headers:{...options.headers,'Idempotency-Key':idempotencyKey}}),
    capabilities:(tenantId:string,threadId:string,options:RequestOptions={})=>transport.request<AttachmentCapabilities>('GET',`${tenant(tenantId)}/chat/threads/${id(threadId)}/attachments/capabilities`,options),
    upload:(tenantId:string,threadId:string,file:Blob,idempotencyKey:string,options:RequestOptions&{filename?:string}={})=>transport.request<AttachmentView>('POST',`${tenant(tenantId)}/chat/threads/${id(threadId)}/attachments`,{...options,body:multipart(file,options.filename),headers:{...options.headers,'Idempotency-Key':idempotencyKey}}),
    list:(tenantId:string,threadId:string,options:RequestOptions&{query?:AttachmentFilter}={})=>transport.request<AttachmentPage>('GET',`${tenant(tenantId)}/chat/threads/${id(threadId)}/attachments`,options),
    get:(tenantId:string,threadId:string,attachmentId:string,options:RequestOptions={})=>transport.request<AttachmentView>('GET',`${tenant(tenantId)}/chat/threads/${id(threadId)}/attachments/${id(attachmentId)}`,options),
    original:(tenantId:string,threadId:string,attachmentId:string,options:RequestOptions={})=>transport.request<BinaryDownload>('GET',`${tenant(tenantId)}/chat/threads/${id(threadId)}/attachments/${id(attachmentId)}/original`,{...options,responseType:'download'}),
    chunks:(tenantId:string,threadId:string,attachmentId:string,options:RequestOptions&{query?:AttachmentChunkFilter}={})=>transport.request<PrivateChunkPage>('GET',`${tenant(tenantId)}/chat/threads/${id(threadId)}/attachments/${id(attachmentId)}/chunks`,options),
    cancel:(tenantId:string,threadId:string,attachmentId:string,input:AttachmentRevision,options:RequestOptions={})=>transport.request<AttachmentView>('POST',`${tenant(tenantId)}/chat/threads/${id(threadId)}/attachments/${id(attachmentId)}/cancel`,{...options,body:input}),
    retry:(tenantId:string,threadId:string,attachmentId:string,input:AttachmentRevision,idempotencyKey:string,options:RequestOptions={})=>transport.request<AttachmentView>('POST',`${tenant(tenantId)}/chat/threads/${id(threadId)}/attachments/${id(attachmentId)}/retry`,{...options,body:input,headers:{...options.headers,'Idempotency-Key':idempotencyKey}}),
    remove:(tenantId:string,threadId:string,attachmentId:string,expectedRevision:number,options:RequestOptions={})=>transport.request<void>('DELETE',`${tenant(tenantId)}/chat/threads/${id(threadId)}/attachments/${id(attachmentId)}`,{...options,query:{expected_revision:expectedRevision}}),
   },
   get:(tenantId:string,threadId:string,options:RequestOptions={})=>transport.request<ChatThread>('GET',`${tenant(tenantId)}/chat/threads/${id(threadId)}`,options),
   update:(tenantId:string,threadId:string,input:ThreadPatch,options:RequestOptions={})=>transport.request<ChatThread>('PATCH',`${tenant(tenantId)}/chat/threads/${id(threadId)}`,{...options,body:input}),
   delete:(tenantId:string,threadId:string,expectedRevision:number,options:RequestOptions={})=>transport.request<void>('DELETE',`${tenant(tenantId)}/chat/threads/${id(threadId)}`,{...options,query:{expected_revision:expectedRevision}}),
   suggestTitle:(tenantId:string,threadId:string,input:TitleRequest,options:RequestOptions={})=>transport.request<TitleSuggestion>('POST',`${tenant(tenantId)}/chat/threads/${id(threadId)}/title-suggestion`,{...options,body:input}),
   folders:{
    get:(tenantId:string,folderId:string,options:RequestOptions={})=>transport.request<ChatFolder>('GET',`${tenant(tenantId)}/chat/folders/${id(folderId)}`,options),
    list:(tenantId:string,options:RequestOptions&{query?:FolderFilter}={})=>transport.request<Page<ChatFolder>>('GET',`${tenant(tenantId)}/chat/folders`,options),
    create:(tenantId:string,input:FolderCreate,options:RequestOptions={})=>transport.request<ChatFolder>('POST',`${tenant(tenantId)}/chat/folders`,{...options,body:input}),
    update:(tenantId:string,folderId:string,input:FolderPatch,options:RequestOptions={})=>transport.request<ChatFolder>('PATCH',`${tenant(tenantId)}/chat/folders/${id(folderId)}`,{...options,body:input}),
    delete:(tenantId:string,folderId:string,expectedRevision:number,options:RequestOptions={})=>transport.request<void>('DELETE',`${tenant(tenantId)}/chat/folders/${id(folderId)}`,{...options,query:{expected_revision:expectedRevision}}),
   },
   threads:(tenantId:string,options:RequestOptions&{query?:ThreadFilter}={})=>transport.request<Page<ChatThread>>('GET',`${tenant(tenantId)}/chat/threads`,options),
   create:(tenantId:string,input:ThreadCreate={},options:RequestOptions={})=>transport.request<ChatThread>('POST',`${tenant(tenantId)}/chat/threads`,{...options,body:input}),
   messages:(tenantId:string,threadId:string,options:RequestOptions&{query?:{before?:string;limit?:number}}={})=>transport.request<Page<ChatMessage>>('GET',`${tenant(tenantId)}/chat/threads/${id(threadId)}/messages`,options),
   submit:(tenantId:string,threadId:string,input:RunInput,options:RequestOptions={})=>transport.request<ChatRun>('POST',`${tenant(tenantId)}/chat/threads/${id(threadId)}/runs`,{...options,body:input}),
   events:(tenantId:string,runId:string,options:RequestOptions&{lastEventId?:string}={})=>{const cursor=options.lastEventId;if(cursor!==undefined&&/[\r\n\0]/.test(cursor))throw new Error('Last-Event-ID cannot contain line breaks or NUL');return transport.stream<ChatEventData>('GET',`${tenant(tenantId)}/chat/runs/${id(runId)}/events`,cursor===undefined?options:{...options,headers:{...options.headers,'Last-Event-ID':cursor}});},
   cancel:(tenantId:string,runId:string,options:RequestOptions={})=>transport.request<ChatRun>('POST',`${tenant(tenantId)}/chat/runs/${id(runId)}/cancel`,options),
   retry:(tenantId:string,runId:string,options:RequestOptions={})=>transport.request<ChatRun>('POST',`${tenant(tenantId)}/chat/runs/${id(runId)}/retry`,options),
   result:(tenantId:string,runId:string,resultId:string,options:RequestOptions={})=>transport.request<EvidenceResult>('GET',`${tenant(tenantId)}/chat/runs/${id(runId)}/results/${id(resultId)}`,options),
  };
}
export type ChatApi=ReturnType<typeof createChatApi>;
