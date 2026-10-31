// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import test from 'node:test';
import {KoinonClient,FetchTransport,KoinonError} from '../dist/index.js';

test('eight query operations retain explicit scope, abort signal, revision and caller keys',async()=>{
 const calls=[];const transport={request:async(method,path,options={})=>{calls.push({method,path,options});return {};}};
 const api=new KoinonClient({transport}).queryBatches;const abort=new AbortController();const options={signal:abort.signal};
 await api.capabilities('north/office','workspace',options);
 await api.create('north/office',{workspace_id:'workspace',items:[{client_item_id:'one',dataset_id:'dataset',question:'Count'}]},'create-key',options);
 await api.list('north/office',{page:2,page_size:3},options);await api.get('north/office','batch/one',options);
 await api.items('north/office','batch/one',{page:2,page_size:3},options);
 await api.result('north/office','batch/one','item/one',options);
 await api.cancel('north/office','batch/one',{expected_revision:7},'cancel-key',options);
 await api.reconcile('south','batch/one','item/one',{expected_revision:8},'inspect-key',options);
 assert.equal(calls.length,8);assert.ok(calls.every(call=>call.options.signal===abort.signal));
 assert.equal(calls[5].path,'/tenants/north%2Foffice/queries/batches/batch%2Fone/items/item%2Fone/result');
 assert.deepEqual(calls[7].options.body,{expected_revision:8});assert.equal(calls[7].options.headers['Idempotency-Key'],'inspect-key');
 assert.ok(calls[7].path.startsWith('/tenants/south/'));
});

test('unknown query mutation has one dispatch and current credential',async()=>{
 let calls=0;const transport=new FetchTransport({baseUrl:'https://inert.test/api/v1',accessToken:()=> 'current-token',fetch:async(url,init)=>{
  calls++;assert.equal(init.headers.get('Authorization'),'Bearer current-token');assert.equal(init.headers.get('Idempotency-Key'),'stable');
  return new Response(JSON.stringify({code:'BULK_QUERY_OUTCOME_UNRESOLVED'}),{status:503});
 }});
 await assert.rejects(()=>new KoinonClient({transport}).queryBatches.reconcile('north','batch','item',{expected_revision:1},'stable'),error=>error instanceof KoinonError&&error.code==='BULK_QUERY_OUTCOME_UNRESOLVED');
 assert.equal(calls,1);
});

test('explicit query key replaces every case variant of inherited headers',async()=>{
 const transport=new FetchTransport({baseUrl:'https://inert.test/api/v1',accessToken:()=> 'token',fetch:async(url,init)=>{
  assert.equal(init.headers.get('Idempotency-Key'),'explicit-key');
  return new Response('{}',{status:200});
 }});
 await new KoinonClient({transport}).queryBatches.cancel('north','batch',{expected_revision:1},'explicit-key',{
  headers:{'idempotency-key':'stale-key','IDEMPOTENCY-KEY':'another-key'},
 });
});
