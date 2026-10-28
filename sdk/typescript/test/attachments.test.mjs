// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {FetchTransport,KoinonClient,KoinonError} from '../dist/index.js';

test('private attachment wire uses multipart, binary, explicit idempotency and revision guards',async()=>{
 const seen=[];let token=0;
 const item={id:'a',tenant_id:'t',thread_id:'thread',filename:'notes.txt',media_type:'text/plain',kind:'document',size_bytes:7,sha256:'a'.repeat(64),status:'queued',revision:2,created_at:'2026-10-27T00:00:00Z',expires_at:'2026-10-28T00:00:00Z',chunk_count:0,progress:{status:'queued',percent:0,attempts:0},warnings:[]};
 const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://example.test/api/v1',accessToken:()=>`fresh-${++token}`,fetch:async(url,init)=>{
  seen.push({url:new URL(url),init});
  if(url.endsWith('/original'))return new Response('private',{headers:{'Content-Type':'text/plain','Content-Disposition':'attachment; filename="notes.txt"','ETag':'"sha"'}});
  if(init.method==='DELETE')return new Response(null,{status:204});
  return new Response(JSON.stringify(item),{headers:{'Content-Type':'application/json'}});
 }})});
 const api=client.chat.attachments;
 await api.upload('tenant/one','thread/one',new Blob(['private'],{type:'text/plain'}),'upload-key',{filename:'notes.txt'});
 await api.list('t','thread',{query:{kind:'image',status:'ready',page:2,page_size:5}});
 await api.get('t','thread','a/one');
 const binary=await api.original('t','thread','a/one');assert.equal(await binary.blob.text(),'private');assert.equal(binary.filename,'notes.txt');
 await api.chunks('t','thread','a/one',{query:{q:'Málaga',page:2}});
 await api.cancel('t','thread','a/one',{expected_revision:2});
 await api.retry('t','thread','a/one',{expected_revision:2},'retry-key');
 await api.remove('t','thread','a/one',2);
 assert.ok(seen[0].init.body instanceof FormData);assert.equal(seen[0].init.body.get('file').name,'notes.txt');assert.equal(seen[0].init.headers.get('Idempotency-Key'),'upload-key');
 assert.deepEqual(JSON.parse(seen[5].init.body),{expected_revision:2});assert.equal(seen[6].init.headers.get('Idempotency-Key'),'retry-key');assert.equal(seen[7].url.searchParams.get('expected_revision'),'2');assert.equal(token,8);
});

test('attachment writes do not retry an unknown server outcome',async()=>{
 let calls=0;const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://example.test/api/v1',accessToken:()=> 'fresh',fetch:async()=>{calls++;return new Response(JSON.stringify({status:503,code:'UNAVAILABLE',detail:'Check the existing attachment before trying again',transactionId:'ref'}),{status:503,headers:{'Content-Type':'application/problem+json'}});}})});
 await assert.rejects(()=>client.chat.attachments.retry('t','thread','a',{expected_revision:2},'same-key'),KoinonError);assert.equal(calls,1);
});
