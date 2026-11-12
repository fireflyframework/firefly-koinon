import type {SourceMappingValidationInput,SourceMappingValidationContinueInput,SourceMappingValidationAbandonInput,SourceMappingValidationOutput,SourceMappingValidationItemPage} from "./generated.js";
import type {SourceCapabilitiesOutput,SourceControlInput,SourceControlOutput,SourceControlReceipt,SourceExistingPolicyReviewInput,SourceMappingOutput,SourceMappingPage,SourcePolicyApplyInput,SourcePolicyOperationOutput,SourcePolicyReceipt,SourcePolicyReviewInput,SourceReviewPage,SourceRunItemPage,SourceRunOutput,SourceRunPage} from "./generated.js";
export type SourceOperationReceipt = SourcePolicyReceipt | SourceControlReceipt;
// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {KoinonTransport,RequestOptions} from './transport.js';
import type {ReaderSourceSelection,ReaderSelectionInput,ReaderSelectionOutput,SourceConnectionOutput,SourceConnectionPage,SourceConnectionRevision,SourceFolderPage,SourceLocationPage} from './generated.js';
export type {ReaderSourceSelection,ReaderSelectionInput,ReaderSelectionOutput,SourceConnectionOutput,SourceConnectionPage,SourceConnectionRevision,SourceFolderPage,SourceLocationPage} from './generated.js';

const id=encodeURIComponent;
const root=(tenant:string)=>`/tenants/${id(tenant)}/content-sources/connections`;
const connection=(tenant:string,value:string)=>`${root(tenant)}/${id(value)}`;
/** Requires the verified owner's identity. Personal tokens cannot manage sources; consent is browser-only. */
export function createContentSourcesApi(transport:KoinonTransport){
 return {
  beginValidation:(tenant:string,input:SourceMappingValidationInput,options:RequestOptions={})=>transport.request<SourceMappingValidationOutput>('POST',`/tenants/${id(tenant)}/content-sources/mapping-validations`,{...options,body:input}),
  validationReceipt:(tenant:string,operation_id:string,options:RequestOptions={})=>transport.request<SourceMappingValidationOutput>('GET',`/tenants/${id(tenant)}/content-sources/mapping-validations/operations/${id(operation_id)}`,{...options}),
  validation:(tenant:string,validation_id:string,options:RequestOptions={})=>transport.request<SourceMappingValidationOutput>('GET',`/tenants/${id(tenant)}/content-sources/mapping-validations/${id(validation_id)}`,{...options}),
  advanceValidation:(tenant:string,validation_id:string,input:SourceMappingValidationContinueInput,options:RequestOptions={})=>transport.request<SourceMappingValidationOutput>('POST',`/tenants/${id(tenant)}/content-sources/mapping-validations/${id(validation_id)}/continue`,{...options,body:input}),
  validationItems:(tenant:string,validation_id:string,filter:{cursor?:string;limit?:number}={},options:RequestOptions={})=>transport.request<SourceMappingValidationItemPage>('GET',`/tenants/${id(tenant)}/content-sources/mapping-validations/${id(validation_id)}/items`,{...options,query:{...filter}}),
  abandonValidation:(tenant:string,validation_id:string,input:SourceMappingValidationAbandonInput,options:RequestOptions={})=>transport.request<SourceMappingValidationOutput>('POST',`/tenants/${id(tenant)}/content-sources/mapping-validations/${id(validation_id)}/abandon`,{...options,body:input}),
  capabilities:(tenant:string,options:RequestOptions={})=>transport.request<SourceCapabilitiesOutput>('GET',`/tenants/${id(tenant)}/content-sources/capabilities`,options),
  mappings:(tenant:string,filter:{limit?:number;cursor?:string}={},options:RequestOptions={})=>transport.request<SourceMappingPage>('GET',`/tenants/${id(tenant)}/content-sources/mappings`,{...options,query:{...filter}}),
  mapping:(tenant:string,mapping_id:string,options:RequestOptions={})=>transport.request<SourceMappingOutput>('GET',`/tenants/${id(tenant)}/content-sources/mappings/${id(mapping_id)}`,{...options}),
  runs:(tenant:string,mapping_id:string,filter:{limit?:number;cursor?:string}={},options:RequestOptions={})=>transport.request<SourceRunPage>('GET',`/tenants/${id(tenant)}/content-sources/mappings/${id(mapping_id)}/runs`,{...options,query:{...filter}}),
  initialOperation:(tenant:string,operation_id:string,filter:{action:string},options:RequestOptions={})=>transport.request<SourceOperationReceipt>('GET',`/tenants/${id(tenant)}/content-sources/operations/${id(operation_id)}`,{...options,query:{...filter}}),
  operation:(tenant:string,mapping_id:string,operation_id:string,filter:{action:string},options:RequestOptions={})=>transport.request<SourceOperationReceipt>('GET',`/tenants/${id(tenant)}/content-sources/mappings/${id(mapping_id)}/operations/${id(operation_id)}`,{...options,query:{...filter}}),
  run:(tenant:string,run_id:string,options:RequestOptions={})=>transport.request<SourceRunOutput>('GET',`/tenants/${id(tenant)}/content-sources/runs/${id(run_id)}`,{...options}),
  runItems:(tenant:string,run_id:string,filter:{limit?:number;cursor?:string}={},options:RequestOptions={})=>transport.request<SourceRunItemPage>('GET',`/tenants/${id(tenant)}/content-sources/runs/${id(run_id)}/items`,{...options,query:{...filter}}),
  cancelRun:(tenant:string,run_id:string,input:SourceControlInput,options:RequestOptions={})=>transport.request<SourceControlOutput>('POST',`/tenants/${id(tenant)}/content-sources/runs/${id(run_id)}/cancel`,{...options,body:input}),
  retryRun:(tenant:string,run_id:string,input:SourceControlInput,options:RequestOptions={})=>transport.request<SourceControlOutput>('POST',`/tenants/${id(tenant)}/content-sources/runs/${id(run_id)}/retry`,{...options,body:input}),
  reviewMapping:(tenant:string,input:SourcePolicyReviewInput,options:RequestOptions={})=>transport.request<SourcePolicyOperationOutput>('POST',`/tenants/${id(tenant)}/content-sources/mapping-reviews`,{...options,body:input}),
  reviewItems:(tenant:string,review_id:string,filter:{limit?:number;cursor?:string}={},options:RequestOptions={})=>transport.request<SourceReviewPage>('GET',`/tenants/${id(tenant)}/content-sources/mapping-reviews/${id(review_id)}/items`,{...options,query:{...filter}}),
  createMapping:(tenant:string,input:SourcePolicyApplyInput,options:RequestOptions={})=>transport.request<SourcePolicyOperationOutput>('POST',`/tenants/${id(tenant)}/content-sources/mappings`,{...options,body:input}),
  reviseMapping:(tenant:string,mapping_id:string,input:SourceExistingPolicyReviewInput,options:RequestOptions={})=>transport.request<SourcePolicyOperationOutput>('POST',`/tenants/${id(tenant)}/content-sources/mappings/${id(mapping_id)}/reviews`,{...options,body:input}),
  applyMapping:(tenant:string,mapping_id:string,input:SourcePolicyApplyInput,options:RequestOptions={})=>transport.request<SourcePolicyOperationOutput>('POST',`/tenants/${id(tenant)}/content-sources/mappings/${id(mapping_id)}/apply`,{...options,body:input}),
  syncMapping:(tenant:string,mapping_id:string,input:SourceControlInput,options:RequestOptions={})=>transport.request<SourceControlOutput>('POST',`/tenants/${id(tenant)}/content-sources/mappings/${id(mapping_id)}/sync`,{...options,body:input}),
  pauseMapping:(tenant:string,mapping_id:string,input:SourceControlInput,options:RequestOptions={})=>transport.request<SourceControlOutput>('POST',`/tenants/${id(tenant)}/content-sources/mappings/${id(mapping_id)}/pause`,{...options,body:input}),
  resumeMapping:(tenant:string,mapping_id:string,input:SourceControlInput,options:RequestOptions={})=>transport.request<SourceControlOutput>('POST',`/tenants/${id(tenant)}/content-sources/mappings/${id(mapping_id)}/resume`,{...options,body:input}),
  retireMapping:(tenant:string,mapping_id:string,input:SourceControlInput,options:RequestOptions={})=>transport.request<SourceControlOutput>('POST',`/tenants/${id(tenant)}/content-sources/mappings/${id(mapping_id)}/retire`,{...options,body:input}),
  readerSelection:(tenant:string,options:RequestOptions={})=>transport.request<ReaderSelectionOutput>('GET',`/tenants/${id(tenant)}/content-sources/reader-selection`,options),
  /** Writes require native browser session authority; a bearer token cannot impersonate it. */
  replaceReaderSelection:(tenant:string,input:ReaderSelectionInput,options:RequestOptions={})=>transport.request<ReaderSelectionOutput>('PUT',`/tenants/${id(tenant)}/content-sources/reader-selection`,{...options,body:input}),
  list:(tenant:string,filter:{cursor?:string;limit?:number}={},options:RequestOptions={})=>transport.request<SourceConnectionPage>('GET',root(tenant),{...options,query:{cursor:filter.cursor,limit:filter.limit}}),
  get:(tenant:string,value:string,options:RequestOptions={})=>transport.request<SourceConnectionOutput>('GET',connection(tenant,value),options),
  disconnect:(tenant:string,value:string,input:SourceConnectionRevision,options:RequestOptions={})=>transport.request<SourceConnectionOutput>('POST',connection(tenant,value)+'/disconnect',{...options,body:{expected_revision:input.expected_revision}}),
  sites:(tenant:string,value:string,filter:{q:string;cursor?:string},options:RequestOptions={})=>transport.request<SourceLocationPage>('GET',connection(tenant,value)+'/sites',{...options,query:{q:filter.q,cursor:filter.cursor}}),
  drives:(tenant:string,value:string,filter:{site_id?:string;cursor?:string}={},options:RequestOptions={})=>transport.request<SourceLocationPage>('GET',connection(tenant,value)+'/drives',{...options,query:{site_id:filter.site_id,cursor:filter.cursor}}),
  children:(tenant:string,value:string,filter:{drive_id:string;folder_id?:string;cursor?:string},options:RequestOptions={})=>transport.request<SourceFolderPage>('GET',connection(tenant,value)+'/children',{...options,query:{drive_id:filter.drive_id,folder_id:filter.folder_id,cursor:filter.cursor}}),
 };
}
export type ContentSourcesApi=ReturnType<typeof createContentSourcesApi>;
