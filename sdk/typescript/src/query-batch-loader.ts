// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {QueryBatchesApi} from './query-batches.js';
import type {KoinonTransport} from './transport.js';

export function createLazyQueryBatchesApi(transport:KoinonTransport):QueryBatchesApi{
 let pending:Promise<QueryBatchesApi>|undefined;
 const load=()=>pending??=import('./query-batches.js').then(
  module=>module.createQueryBatchesApi(transport),
  (error:unknown)=>{pending=undefined;throw error;},
 );
 const delegate=<Args extends unknown[],Result>(select:(api:QueryBatchesApi)=>(...args:Args)=>Promise<Result>)=>async(...args:Args):Promise<Result>=>select(await load())(...args);
 return {
  capabilities:delegate(api=>api.capabilities), create:delegate(api=>api.create), list:delegate(api=>api.list),
  get:delegate(api=>api.get), items:delegate(api=>api.items), result:delegate(api=>api.result),
  cancel:delegate(api=>api.cancel), reconcile:delegate(api=>api.reconcile),
 };
}
