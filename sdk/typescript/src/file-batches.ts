// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type * as G from './generated.js';
import type {KoinonTransport,RequestOptions} from './transport.js';
export interface FileBatchPageFilter {page?:number;page_size?:number}
const id=(value:string)=>encodeURIComponent(value);
const prefix=(tenantId:string)=>`/tenants/${id(tenantId)}`;
const batch=(tenantId:string,batchId:string)=>`${prefix(tenantId)}/sources/batches/${id(batchId)}`;
const item=(tenantId:string,batchId:string,itemId:string)=>`${batch(tenantId,batchId)}/items/${id(itemId)}`;
const keyed=(options:RequestOptions,key:string):RequestOptions=>{
 const headers={...options.headers};
 for(const name of Object.keys(headers))if(name.toLowerCase()==='idempotency-key')delete headers[name];
 return {...options,headers:{...headers,'Idempotency-Key':key}};
};
export function createFileBatchesApi(transport:KoinonTransport){return {
 capabilities:(tenantId:string,workspaceId:string,options:RequestOptions={})=>transport.request<G.FileBatchCapabilities>('GET',`${prefix(tenantId)}/source-batch-capabilities`,{...options,query:{workspace_id:workspaceId}}),
 create:(tenantId:string,input:G.FileBatchCreate,key:string,options:RequestOptions={})=>transport.request<G.FileBatchView>('POST',`${prefix(tenantId)}/sources/batches`,{...keyed(options,key),body:input}),
 list:(tenantId:string,filter:FileBatchPageFilter={},options:RequestOptions={})=>transport.request<G.FileBatchPage>('GET',`${prefix(tenantId)}/sources/batches`,{...options,query:{...filter}}),
 get:(tenantId:string,batchId:string,options:RequestOptions={})=>transport.request<G.FileBatchView>('GET',batch(tenantId,batchId),options),
 items:(tenantId:string,batchId:string,filter:FileBatchPageFilter={},options:RequestOptions={})=>transport.request<G.FileItemPage>('GET',`${batch(tenantId,batchId)}/items`,{...options,query:{...filter}}),
 upload:(tenantId:string,batchId:string,itemId:string,content:Blob,key:string,options:RequestOptions={})=>{
  if(content.size<1||content.size>33554432)throw new Error('Original content must be1..33554432bytes');
  const request=keyed(options,key);const headers={...request.headers};
  for(const name of Object.keys(headers))if(name.toLowerCase()==='content-type')delete headers[name];
  return transport.request<G.StagedFileReceipt>('PUT',`${item(tenantId,batchId,itemId)}/content`,{...request,body:content,headers:{...headers,'Content-Type':'application/octet-stream'}});
 },
 receipt:(tenantId:string,batchId:string,itemId:string,options:RequestOptions={})=>transport.request<G.StagedFileReceipt>('GET',`${item(tenantId,batchId,itemId)}/receipt`,options),
 submit:(tenantId:string,batchId:string,input:G.BulkAction,key:string,options:RequestOptions={})=>transport.request<G.FileBatchView>('POST',`${batch(tenantId,batchId)}/submit`,{...keyed(options,key),body:input}),
 cancel:(tenantId:string,batchId:string,input:G.BulkAction,key:string,options:RequestOptions={})=>transport.request<G.FileBatchView>('POST',`${batch(tenantId,batchId)}/cancel`,{...keyed(options,key),body:input}),
 reconcile:(tenantId:string,batchId:string,itemId:string,input:G.BulkAction,key:string,options:RequestOptions={})=>transport.request<G.FileBatchView>('POST',`${item(tenantId,batchId,itemId)}/reconcile`,{...keyed(options,key),body:input}),
 recoverOriginal:(tenantId:string,batchId:string,itemId:string,input:G.BulkAction,key:string,options:RequestOptions={})=>transport.request<G.FileBatchView>('POST',`${item(tenantId,batchId,itemId)}/original/reconcile`,{...keyed(options,key),body:input}),
};}
export type FileBatchesApi=ReturnType<typeof createFileBatchesApi>;
