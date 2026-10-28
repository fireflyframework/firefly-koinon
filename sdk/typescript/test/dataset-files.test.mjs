// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {KoinonClient,FetchTransport} from '../dist/index.js';

test('append retains dataset identity and sends exactly one binary multipart field',async()=>{
 const calls=[];
 const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://koinon.test/api/v1',accessToken:()=> 'fresh',fetch:async(url,init)=>{
  calls.push({url,init});
  assert.ok(init.body instanceof FormData);
  assert.deepEqual([...init.body.keys()],['file']);
  assert.equal(await init.body.get('file').text(),'x\n2');
  assert.equal(init.body.get('file').name,'more.csv');
  return new Response(JSON.stringify({dataset_id:'data/set',file_version_id:'version',filename:'more.csv',sha256:'a'.repeat(64),byte_size:3,table_ids:['one','two'],status:'ready'}),{status:201,headers:{'Content-Type':'application/json'}});
 }})});
 const result=await client.dataset.appendFile('north','data/set',new Blob(['x\n2']),'stable-request',{filename:'more.csv'});
 assert.deepEqual(result.table_ids,['one','two']);
 assert.ok(calls[0].url.endsWith('/datasets/data%2Fset/files'));
 assert.equal(calls[0].init.headers.get('Authorization'),'Bearer fresh');
 assert.equal(calls[0].init.headers.get('Idempotency-Key'),'stable-request');
 assert.equal(calls[0].init.headers.has('Content-Type'),false);
});
