// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import test from 'node:test';
import {KoinonClient,FetchTransport,KoinonError} from '../dist/index.js';

test('all batch operations bind explicit paths, revision, caller key and cancellation',async()=>{
 const calls=[];const transport={request:async(method,path,options={})=>{calls.push({method,path,options});return {};}};
 const api=new KoinonClient({transport}).fileBatches;const controller=new AbortController();const options={signal:controller.signal};
 await api.capabilities('north/office','workspace',options);
 await api.create('north/office',{destination:{workspace_id:'w',project_id:'p',parent_id:'c'},items:[{client_item_id:'one',filename:'facts.csv',mode:'dataset',size_bytes:8,sha256:'a'.repeat(64)}]},'create-key',options);
 await api.list('north/office',{page:2,page_size:3},options);
 await api.get('north/office','batch/one',options);
 await api.items('north/office','batch/one',{page:2,page_size:3},options);
 const content=new Blob(['original']);await api.upload('north/office','batch/one','item/one',content,'upload-key',options);
 await api.receipt('north/office','batch/one','item/one',options);
 const action={expected_revision:7};
 await api.submit('north/office','batch/one',action,'submit-key',options);
 await api.cancel('north/office','batch/one',action,'cancel-key',options);
 await api.reconcile('north/office','batch/one','item/one',action,'inspect-key',options);
 await api.recoverOriginal('south','batch/one','item/one',action,'original-key',options);
 assert.equal(calls.length,11);assert.ok(calls.every(call=>call.options.signal===controller.signal));
 assert.equal(calls[5].path,'/tenants/north%2Foffice/sources/batches/batch%2Fone/items/item%2Fone/content');
 assert.equal(calls[5].options.body,content);assert.equal(calls[5].options.headers['Content-Type'],'application/octet-stream');
 assert.deepEqual(calls[9].options.body,{expected_revision:7});assert.ok(calls[10].path.startsWith('/tenants/south/'));
});

test('raw upload preserves bytes and uncertain response is never retried',async()=>{
 let calls=0;const blob=new Blob(['original']);
 const transport=new FetchTransport({baseUrl:'https://inert.test/api/v1',accessToken:()=> 'current-token',fetch:async(url,init)=>{
  calls++;assert.equal(init.method,'PUT');assert.equal(init.body,blob);assert.equal(init.headers.get('Content-Type'),'application/octet-stream');
  assert.equal(init.headers.get('Idempotency-Key'),'stable-key');assert.equal(init.redirect,'error');
  return new Response(JSON.stringify({code:'BULK_NATIVE_OUTCOME_UNRESOLVED',detail:'Inspect retained receipt'}),{status:503});
 }});
 await assert.rejects(()=>new KoinonClient({transport}).fileBatches.upload('north','batch','item',blob,'stable-key'),error=>error instanceof KoinonError&&error.code==='BULK_NATIVE_OUTCOME_UNRESOLVED');
 assert.equal(calls,1);
});

test('explicit original key and content type replace inherited case variants',async()=>{
 const transport=new FetchTransport({baseUrl:'https://inert.test/api/v1',accessToken:()=> 'token',fetch:async(url,init)=>{
  assert.equal(init.headers.get('Idempotency-Key'),'explicit-key');
  assert.equal(init.headers.get('Content-Type'),'application/octet-stream');
  return new Response('{}',{status:200});
 }});
 await new KoinonClient({transport}).fileBatches.upload('north','batch','item',new Blob(['original']),'explicit-key',{
  headers:{'idempotency-key':'stale-key','content-type':'text/plain','CONTENT-TYPE':'application/json'},
 });
});
