// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {OrganizationPerson,OrganizationPersonCreate,OrganizationPersonPatch,OrganizationPersonPage,OrganizationUnit,OrganizationUnitInput,OrganizationUnitPatch,OrganizationUnitPage,OrganizationDirectorySettings,OrganizationDirectorySettingsInput,OrganizationProfileMapping,OrganizationProfileMappingInput} from './generated.js';
import type {OrganizationPeopleFilter,OrganizationUnitFilter,OrganizationReportsFilter} from './types.js';
import type {KoinonTransport,RequestOptions,BinaryDownload} from './transport.js';
const id=encodeURIComponent;
const tenant=(tenantId:string)=>`/tenants/${id(tenantId)}`;

export function createOrganizationPeopleApi(transport:KoinonTransport){
 return {
   me:(tenantId:string,filter:{workspace_id?:string}={},options:RequestOptions={})=>transport.request<OrganizationPerson>('GET',`${tenant(tenantId)}/organization/people/me`,{...options,query:{...filter}}),
   list:(tenantId:string,filter:OrganizationPeopleFilter={},options:RequestOptions={})=>transport.request<OrganizationPersonPage>('GET',`${tenant(tenantId)}/organization/people`,{...options,query:{...filter}}),
   create:(tenantId:string,input:OrganizationPersonCreate,options:RequestOptions={})=>transport.request<OrganizationPerson>('POST',`${tenant(tenantId)}/organization/people`,{...options,body:input}),
   get:(tenantId:string,personId:string,filter:{workspace_id?:string}={},options:RequestOptions={})=>transport.request<OrganizationPerson>('GET',`${tenant(tenantId)}/organization/people/${id(personId)}`,{...options,query:{...filter}}),
   update:(tenantId:string,personId:string,input:OrganizationPersonPatch,options:RequestOptions={})=>transport.request<OrganizationPerson>('PATCH',`${tenant(tenantId)}/organization/people/${id(personId)}`,{...options,body:input}),
   avatar:(tenantId:string,personId:string,filter:{workspace_id?:string}={},options:RequestOptions={})=>transport.request<BinaryDownload>('GET',`${tenant(tenantId)}/organization/people/${id(personId)}/avatar`,{...options,query:{...filter},responseType:'download'}),
   reports:(tenantId:string,personId:string,filter:OrganizationReportsFilter={},options:RequestOptions={})=>transport.request<OrganizationPersonPage>('GET',`${tenant(tenantId)}/organization/people/${id(personId)}/reports`,{...options,query:{...filter}}),
   units:(tenantId:string,filter:OrganizationUnitFilter={},options:RequestOptions={})=>transport.request<OrganizationUnitPage>('GET',`${tenant(tenantId)}/organization/units`,{...options,query:{...filter}}),
   createUnit:(tenantId:string,input:OrganizationUnitInput,options:RequestOptions={})=>transport.request<OrganizationUnit>('POST',`${tenant(tenantId)}/organization/units`,{...options,body:input}),
   updateUnit:(tenantId:string,unitId:string,input:OrganizationUnitPatch,options:RequestOptions={})=>transport.request<OrganizationUnit>('PATCH',`${tenant(tenantId)}/organization/units/${id(unitId)}`,{...options,body:input}),
   deleteUnit:(tenantId:string,unitId:string,expectedRevision:number,options:RequestOptions={})=>transport.request<void>('DELETE',`${tenant(tenantId)}/organization/units/${id(unitId)}`,{...options,query:{expected_revision:expectedRevision}}),
   settings:(tenantId:string,options:RequestOptions={})=>transport.request<OrganizationDirectorySettings>('GET',`${tenant(tenantId)}/organization/directory-settings`,options),
   updateSettings:(tenantId:string,input:OrganizationDirectorySettingsInput,options:RequestOptions={})=>transport.request<OrganizationDirectorySettings>('PATCH',`${tenant(tenantId)}/organization/directory-settings`,{...options,body:input}),
   mapping:(tenantId:string,providerId:string,options:RequestOptions={})=>transport.request<OrganizationProfileMapping>('GET',`${tenant(tenantId)}/organization/profile-mappings/${id(providerId)}`,options),
   updateMapping:(tenantId:string,providerId:string,input:OrganizationProfileMappingInput,options:RequestOptions={})=>transport.request<OrganizationProfileMapping>('PUT',`${tenant(tenantId)}/organization/profile-mappings/${id(providerId)}`,{...options,body:input}),
  };
}
export type OrganizationPeopleApi=ReturnType<typeof createOrganizationPeopleApi>;
