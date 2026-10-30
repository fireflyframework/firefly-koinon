// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {OrganizationPeopleApi} from './organization-people.js';
import type {KoinonTransport} from './transport.js';

export function createLazyOrganizationPeopleApi(transport:KoinonTransport):OrganizationPeopleApi{
 let pending:Promise<OrganizationPeopleApi>|undefined;
 const load=()=>pending??=import('./organization-people.js').then(
  module=>module.createOrganizationPeopleApi(transport),
  (error:unknown)=>{pending=undefined;throw error;},
 );
 const delegate=<Args extends unknown[],Result>(select:(api:OrganizationPeopleApi)=>(...args:Args)=>Promise<Result>)=>async(...args:Args):Promise<Result>=>select(await load())(...args);
 return {
  me:delegate(api=>api.me),
  list:delegate(api=>api.list),
  get:delegate(api=>api.get),
  create:delegate(api=>api.create),
  update:delegate(api=>api.update),
  avatar:delegate(api=>api.avatar),
  reports:delegate(api=>api.reports),
  units:delegate(api=>api.units),
  createUnit:delegate(api=>api.createUnit),
  updateUnit:delegate(api=>api.updateUnit),
  deleteUnit:delegate(api=>api.deleteUnit),
  settings:delegate(api=>api.settings),
  updateSettings:delegate(api=>api.updateSettings),
  mapping:delegate(api=>api.mapping),
  updateMapping:delegate(api=>api.updateMapping),
 };
}
