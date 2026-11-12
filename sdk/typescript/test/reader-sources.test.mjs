// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {KoinonClient,FetchTransport} from '../dist/index.js';
import {createContentSourcesApi} from '../dist/content-sources.js';

test('reader detail POST preserves local-only body and binary download metadata',async()=>{
 const requests=[];
 const app=createServer(async(req,res)=>{
  let body='';for await(const part of req)body+=part;
  requests.push({path:req.url,method:req.method,body:JSON.parse(body)});
  if(req.url.endsWith('/original/read')){
   res.setHeader('Content-Type','application/pdf');
   res.setHeader('Content-Disposition','attachment; filename="source.pdf"');
   res.end('original bytes');
  }else {res.setHeader('Content-Type','application/json');res.end(JSON.stringify({id:'entry',name:'Local'}));}
 });
 await new Promise(resolve=>app.listen(0,'127.0.0.1',resolve));
 try{
  const client=new KoinonClient({transport:new FetchTransport({baseUrl:`http://127.0.0.1:${app.address().port}/api/v1`})});
  const entry=await client.catalog.read('north','entry',{reader_source_connections:[]});
  const file=await client.documents.readOriginal('north','entry',{reader_source_connections:[]});
  assert.equal(entry.name,'Local');
  assert.equal(file.filename,'source.pdf');
  assert.equal(await file.blob.text(),'original bytes');
  assert.deepEqual(requests.map(r=>r.path),['/api/v1/tenants/north/catalog/entry/read','/api/v1/tenants/north/documents/entry/original/read']);
  assert.ok(requests.every(r=>r.method==='POST'&&Array.isArray(r.body.reader_source_connections)&&r.body.reader_source_connections.length===0));
 }finally{await new Promise(resolve=>app.close(resolve));}
});

test('queued chat preserves omitted, explicit and local-only source choices',async()=>{
 const requests=[];
 const client=new KoinonClient({transport:{request:async(method,path,options)=>{
  requests.push({method,path,body:JSON.parse(JSON.stringify(options.body))});
  return {run_id:'run',message_id:'message',event_cursor:'0'};
 }}});
 const value={agent_id:'agent',message:'Question',client_request_id:'request'};
 for(const choices of [undefined,[],[{provider:'google_drive',connection_id:'reader'}]]){
  const result=await client.chat.submit('north','thread',{...value,reader_source_connections:choices});
  assert.equal(result.run_id,'run');
 }
 assert.equal(Object.hasOwn(requests[0].body,'reader_source_connections'),false);
 assert.deepEqual(requests[1].body.reader_source_connections,[]);
 assert.deepEqual(requests[2].body.reader_source_connections,[{provider:'google_drive',connection_id:'reader'}]);
 assert.ok(requests.every(request=>request.path==='/tenants/north/chat/threads/thread/runs'&&request.method==='POST'));
});

test('history and shares browse preserve paths and unknown totals',async()=>{
 const requests=[];
 const transport={request:async(method,path,options)=>{requests.push({method,path,...options});return {items:[],next_cursor:'c'.repeat(43),total:null,total_is_exact:false};}};
 const client=new KoinonClient({transport});
 const history=await client.chat.browse('north',{reader_source_connections:[]});
 const shares=await client.shares.browse('north',{reader_source_connections:[{provider:'google_drive',connection_id:'reader'}]});
 assert.equal(requests[0].path,'/tenants/north/chat/threads/browse');
 assert.equal(requests[1].path,'/tenants/north/shares/browse');
 assert.deepEqual(requests[0].body.reader_source_connections,[]);
 assert.equal(requests[1].body.reader_source_connections[0].connection_id,'reader');
 assert.equal(history.total,null);assert.equal(shares.total_is_exact,false);
 assert.ok(requests.every(request=>request.method==='POST'));
});

test('reader choices preserve omission and explicit empty through authenticated HTTP and cursor pages',async()=>{
 const requests=[];
 const app=createServer(async(req,res)=>{
  let body='';for await(const part of req)body+=part;
  requests.push({path:req.url,method:req.method,body:body?JSON.parse(body):null,token:req.headers.authorization});
  res.setHeader('Content-Type','application/json');
  res.end(JSON.stringify(req.url.endsWith('reader-selection')?{revision:1,connections:[]}:{items:[],actors:{},next_cursor:'b'.repeat(43),total:null,total_is_exact:false}));
 });
 await new Promise(resolve=>app.listen(0,'127.0.0.1',resolve));
 try{
  const transport=new FetchTransport({baseUrl:`http://127.0.0.1:${app.address().port}/api/v1`,accessToken:()=> 'reader'});
  const client=new KoinonClient({transport});
  await client.search('north',{question:'Q'});
  await client.search('north',{question:'Q',reader_source_connections:[]});
  await client.query('north',{dataset_id:'dataset',sql:'SELECT 1',reader_source_connections:[]});
  const page=await client.catalog.browse('north',{cursor:'a'.repeat(43),reader_source_connections:[]});
  await client.exports.browse('north',{reader_source_connections:[]});
  const sources=createContentSourcesApi(transport);
  await sources.readerSelection('north');
  await sources.replaceReaderSelection('north',{expected_revision:0,operation_id:'21908677-4a5a-4439-9858-1b32a6382c60',connections:[]});
  assert.equal(Object.hasOwn(requests[0].body,'reader_source_connections'),false);
  for(const index of [1,2,3,4])assert.deepEqual(requests[index].body.reader_source_connections,[]);
  assert.equal(page.total,null);assert.equal(page.total_is_exact,false);assert.equal(page.next_cursor,'b'.repeat(43));
  assert.equal(requests[3].path,'/api/v1/tenants/north/catalog/browse');
  assert.equal(requests[4].path,'/api/v1/tenants/north/exports/browse');
  assert.equal(requests[5].method,'GET');assert.equal(requests[6].method,'PUT');
  assert.deepEqual(requests[6].body.connections,[]);
  assert.equal(requests.length,7);assert.ok(requests.every(request=>request.token==='Bearer reader'));
 }finally{await new Promise(resolve=>app.close(resolve));}
});
