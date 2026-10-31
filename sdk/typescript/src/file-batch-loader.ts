// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {FileBatchesApi} from './file-batches.js';
import type {KoinonTransport} from './transport.js';

export function createLazyFileBatchesApi(transport:KoinonTransport):FileBatchesApi{
 let pending:Promise<FileBatchesApi>|undefined;
 const load=()=>pending??=import('./file-batches.js').then(
  module=>module.createFileBatchesApi(transport),
  (error:unknown)=>{pending=undefined;throw error;},
 );
 const delegate=<Args extends unknown[],Result>(select:(api:FileBatchesApi)=>(...args:Args)=>Promise<Result>)=>async(...args:Args):Promise<Result>=>select(await load())(...args);
 return {
  capabilities:delegate(api=>api.capabilities),
  create:delegate(api=>api.create),
  list:delegate(api=>api.list),
  get:delegate(api=>api.get),
  items:delegate(api=>api.items),
  upload:delegate(api=>api.upload),
  receipt:delegate(api=>api.receipt),
  submit:delegate(api=>api.submit),
  cancel:delegate(api=>api.cancel),
  reconcile:delegate(api=>api.reconcile),
  recoverOriginal:delegate(api=>api.recoverOriginal),
 };
}
