// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {FetchTransport,KoinonClient} from '../dist/index.js';

test('canonical content and knowledge assignment helpers preserve preconditions and explicit null',async()=>{
 const seen=[];
 const client=new KoinonClient({transport:{request:async(method,path,options)=>{seen.push({method,path,options});return {};}}});
 await client.documents.replace('t','doc/one',new Blob(['updated']),{filename:'evidence.txt',expected_sha256:'digest',acknowledge_chunk_invalidation:true});
 await client.documents.reingest('t','doc/one',{expected_sha256:'digest',acknowledge_chunk_invalidation:false});
 await client.knowledgeConnections.update('t','conn',{domain:'documents',role:'documents.answer',workspace_id:null,expected_revision:2});
 assert.equal(seen[0].options.headers['If-Match'],'"digest"');
 assert.equal(seen[0].options.body.get('acknowledge_chunk_invalidation'),'true');
 assert.deepEqual(seen[1].options.body,{acknowledge_chunk_invalidation:false});
 assert.equal(seen[2].options.body.workspace_id,null);
 assert.equal(seen[0].path,'/tenants/t/documents/doc%2Fone/content');
});

test('binary download retains response metadata and authenticated304',async()=>{
 const calls=[];
 const transport=new FetchTransport({baseUrl:'https://api.example/api/v1',accessToken:()=> 'fresh',fetch:async(url,init)=>{
  calls.push(init);
  return new Response(calls.length===1?'original':null,{status:calls.length===1?200:304,headers:{ETag:'"hash"','Content-Type':'text/plain','Content-Disposition':"attachment; filename*=UTF-8''evidence%20one.txt"}});
 }});
 const first=await transport.request('GET','/x',{responseType:'download'});
 const cached=await transport.request('GET','/x',{responseType:'download',headers:{'If-None-Match':first.etag}});
 assert.equal(await first.blob.text(),'original');
 assert.equal(first.filename,'evidence one.txt');
 assert.equal(cached.not_modified,true);
 assert.equal(calls[1].headers.get('Authorization'),'Bearer fresh');
});

test('canonical operation map resolves helpers and precision strings are unchanged',async()=>{
 const {readFile}=await import('node:fs/promises');
 const contract=JSON.parse(await readFile(new URL('../../contract/operations.json',import.meta.url),'utf8'));
 const client=new KoinonClient({transport:{request:async()=>({}),stream:async function*(){}}});
 assert.equal(contract.canonical_operation_count,contract.operations.length);
 for(const operation of contract.operations){let value=client;for(const part of operation.sdk_typescript.split('.'))value=value[part];assert.equal(typeof value,'function',operation.operation);}
 const seen=[];
 const transport=new FetchTransport({baseUrl:'https://example.test/api/v1',accessToken:()=> 'fresh',fetch:async(url,init)=>{
  seen.push({url,init});return new Response(JSON.stringify({query_id:'q',execution_status:'OK',preview:[{positive:'9007199254740993',negative:'-9007199254740993',decimal:'-0.1234567890123456789',safe:9007199254740991,flag:false,nested:[null,'18446744073709551615']}]}),{headers:{'Content-Type':'application/json'}});
 }});
 const response=await new KoinonClient({transport}).query('t',{dataset_id:'d',sql:'SELECT 1'});
 assert.equal(response.preview[0].positive,'9007199254740993');
 assert.equal(response.preview[0].negative,'-9007199254740993');
 assert.equal(response.preview[0].decimal,'-0.1234567890123456789');
 assert.equal(response.preview[0].flag,false);
 await transport.request('GET','/x',{query:{include_archived:false,page:2}});
 assert.match(seen[1].url,/include_archived=false/);
});
