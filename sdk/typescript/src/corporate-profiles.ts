// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type * as G from './generated.js';
import type {KoinonTransport,RequestOptions} from './transport.js';

export interface OrganizationScopeFilter {workspace_id?:string}

const id=(value:string)=>encodeURIComponent(value);
const tenant=(value:string)=>`/tenants/${id(value)}`;
export function createCorporateProfilesApi(transport:KoinonTransport){
 return {
  presentation:(tenantId:string,filter:OrganizationScopeFilter={},options:RequestOptions={})=>transport.request<G.OrganizationPresentation>('GET',`${tenant(tenantId)}/organization/people/me/presentation`,{...options,query:{...filter}}),
  updatePresentation:(tenantId:string,input:G.OrganizationPresentationInput,filter:OrganizationScopeFilter={},options:RequestOptions={})=>transport.request<G.OrganizationPresentation>('PATCH',`${tenant(tenantId)}/organization/people/me/presentation`,{...options,body:input,query:{...filter}}),
  refreshSelf:(tenantId:string,input:G.CorporateProfileRefreshInput={},filter:OrganizationScopeFilter={},options:RequestOptions={})=>transport.request<G.CorporateProfileRefresh>('POST',`${tenant(tenantId)}/organization/people/me/profile-refresh`,{...options,body:input,query:{...filter}}),
  refreshPerson:(tenantId:string,personId:string,input:G.CorporateProfileRefreshInput={},filter:OrganizationScopeFilter={},options:RequestOptions={})=>transport.request<G.CorporateProfileRefresh>('POST',`${tenant(tenantId)}/organization/people/${id(personId)}/profile-refresh`,{...options,body:input,query:{...filter}}),
 };
}
export type CorporateProfilesApi=ReturnType<typeof createCorporateProfilesApi>;
