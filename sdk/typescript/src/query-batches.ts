// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type * as G from './generated.js';
import type {KoinonTransport,RequestOptions} from './transport.js';
export interface QueryBatchPageFilter {page?:number;page_size?:number}
const id=(value:string)=>encodeURIComponent(value);
const prefix=(tenantId:string)=>`/tenants/${id(tenantId)}`;
const batch=(tenantId:string,batchId:string)=>`${prefix(tenantId)}/queries/batches/${id(batchId)}`;
const item=(tenantId:string,batchId:string,itemId:string)=>`${batch(tenantId,batchId)}/items/${id(itemId)}`;
const keyed=(options:RequestOptions,key:string):RequestOptions=>{
 const headers={...options.headers};
 for(const name of Object.keys(headers))if(name.toLowerCase()==='idempotency-key')delete headers[name];
 return {...options,headers:{...headers,'Idempotency-Key':key}};
};
export function createQueryBatchesApi(transport:KoinonTransport){return {
 capabilities:(tenantId:string,workspaceId:string,options:RequestOptions={})=>transport.request<G.QueryBatchCapabilities>('GET',`${prefix(tenantId)}/query-batch-capabilities`,{...options,query:{workspace_id:workspaceId}}),
 create:(tenantId:string,input:G.QueryBatchCreate,key:string,options:RequestOptions={})=>transport.request<G.QueryBatchView>('POST',`${prefix(tenantId)}/queries/batches`,{...keyed(options,key),body:input}),
 list:(tenantId:string,filter:QueryBatchPageFilter={},options:RequestOptions={})=>transport.request<G.QueryBatchPage>('GET',`${prefix(tenantId)}/queries/batches`,{...options,query:{...filter}}),
 get:(tenantId:string,batchId:string,options:RequestOptions={})=>transport.request<G.QueryBatchView>('GET',batch(tenantId,batchId),options),
 items:(tenantId:string,batchId:string,filter:QueryBatchPageFilter={},options:RequestOptions={})=>transport.request<G.QueryBatchItemPage>('GET',`${batch(tenantId,batchId)}/items`,{...options,query:{...filter}}),
 result:(tenantId:string,batchId:string,itemId:string,options:RequestOptions={})=>transport.request<G.QueryBatchResult>('GET',`${item(tenantId,batchId,itemId)}/result`,options),
 cancel:(tenantId:string,batchId:string,input:G.QueryBatchAction,key:string,options:RequestOptions={})=>transport.request<G.QueryBatchCancellation>('POST',`${batch(tenantId,batchId)}/cancel`,{...keyed(options,key),body:input}),
 reconcile:(tenantId:string,batchId:string,itemId:string,input:G.QueryBatchAction,key:string,options:RequestOptions={})=>transport.request<G.QueryBatchView>('POST',`${item(tenantId,batchId,itemId)}/reconcile`,{...keyed(options,key),body:input}),
};}
export type QueryBatchesApi=ReturnType<typeof createQueryBatchesApi>;
