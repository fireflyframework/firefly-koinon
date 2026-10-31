// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {CorporateProfilesApi} from './corporate-profiles.js';
import type {KoinonTransport} from './transport.js';

export function createLazyCorporateProfilesApi(transport:KoinonTransport):CorporateProfilesApi{
 let pending:Promise<CorporateProfilesApi>|undefined;
 const load=()=>pending??=import('./corporate-profiles.js').then(
  module=>module.createCorporateProfilesApi(transport),
  (error:unknown)=>{pending=undefined;throw error;},
 );
 const delegate=<Args extends unknown[],Result>(select:(api:CorporateProfilesApi)=>(...args:Args)=>Promise<Result>)=>async(...args:Args):Promise<Result>=>select(await load())(...args);
 return {
  presentation:delegate(api=>api.presentation),
  updatePresentation:delegate(api=>api.updatePresentation),
  refreshSelf:delegate(api=>api.refreshSelf),
  refreshPerson:delegate(api=>api.refreshPerson),
 };
}
