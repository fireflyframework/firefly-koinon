// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createServer} from 'node:http';
import {KoinonClient, FetchTransport, KoinonError} from '../dist/index.js';
async function server(handler, run) {
 const app=createServer(handler);await new Promise(resolve=>app.listen(0,'127.0.0.1',resolve));
 try {await run(`http://127.0.0.1:${app.address().port}/bff/api/v1`);}
 finally {await new Promise(resolve=>app.close(resolve));}
}
test('scoped catalog preserves identifiers and caller credentials',async()=>{
 await server((req,res)=>{
  assert.equal(req.url,'/bff/api/v1/tenants/north%2Fdivision/catalog?kind=document');
  assert.equal(req.headers.authorization,'Bearer caller-scoped');
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify({items:[]}));
 },async baseUrl=>{
  const client=new KoinonClient({transport:new FetchTransport({baseUrl,accessToken:()=> 'caller-scoped'})});
  assert.deepEqual(await client.catalog.list('north/division',{kind:'document'}),{items:[]});
 });
});
test('BFF writes apply fresh CSRF without browser globals',async()=>{
 await server((req,res)=>{
  assert.equal(req.headers['x-xsrf-token'],'csrf-from-host');assert.equal(req.headers.authorization,undefined);
  assert.equal(req.method,'POST');let raw='';req.on('data',part=>raw+=part);req.on('end',()=>{
   assert.equal(JSON.parse(raw).name,'Research');
   res.setHeader('Content-Type','application/json');res.end(JSON.stringify({id:'workspace-1'}));
  });
 },async baseUrl=>{
  const client=new KoinonClient({transport:new FetchTransport({baseUrl,csrfToken:()=> 'csrf-from-host'})});
  assert.equal((await client.catalog.create('north',{kind:'workspace',name:'Research'})).id,'workspace-1');
 });
});
test('problem details preserve status code and request identity',async()=>{
 await server((req,res)=>{
  res.statusCode=403;res.setHeader('Content-Type','application/problem+json');
  res.end(JSON.stringify({title:'Forbidden',detail:'Membership required',code:'ACCESS_DENIED',request_id:'trace-1'}));
 },async baseUrl=>{
  const client=new KoinonClient({transport:new FetchTransport({baseUrl})});
  await assert.rejects(client.context(),e=>e instanceof KoinonError&&e.status===403&&e.code==='ACCESS_DENIED'&&e.requestId==='trace-1');
 });
});
test('SSE preserves split UTF-8 frames, multiline data, event IDs and cancellation',async()=>{
 await server((req,res)=>{
  assert.equal(req.headers.accept,'text/event-stream');
  assert.equal(req.headers.authorization,'Bearer stream-token');
  assert.equal(req.headers['last-event-id'],'8');
  res.writeHead(200,{'Content-Type':'text/event-stream'});
  const bytes=Buffer.from(': heartbeat\r\nid: 9\r\nevent: message_delta\r\ndata: {"text":\r\ndata: "conocimiento ñ"}\r\n\r\nid: 10\nevent: completed\ndata: {"status":"completed"}\n\n');
  res.write(bytes.subarray(0,bytes.indexOf(0xc3)+1));
  setTimeout(()=>res.end(bytes.subarray(bytes.indexOf(0xc3)+1)),5);
 },async baseUrl=>{
  const transport=new FetchTransport({baseUrl,accessToken:()=> 'stream-token'});
  const events=[];
  for await(const event of transport.stream('GET','/chat/runs/run-1/events',{headers:{'Last-Event-ID':'8'}}))events.push(event);
  assert.deepEqual(events,[{id:'9',type:'message_delta',data:{text:'conocimiento ñ'}},{id:'10',type:'completed',data:{status:'completed'}}]);
 });
});
test('SSE rejects non-stream success and retains structured authentication failures',async()=>{
 await server((req,res)=>{
  if(req.url.endsWith('/bad')){res.setHeader('Content-Type','application/json');res.end('{}');return;}
  res.writeHead(403,{'Content-Type':'application/problem+json'});res.end('{"code":"ACCESS_DENIED","detail":"Membership revoked"}');
 },async baseUrl=>{
  const transport=new FetchTransport({baseUrl});
  await assert.rejects(async()=>{for await(const e of transport.stream('GET','/bad'))void e;},/event-stream/);
  await assert.rejects(async()=>{for await(const e of transport.stream('GET','/denied'))void e;},e=>e instanceof KoinonError&&e.code==='ACCESS_DENIED');
 });
});
test('avatar transport preserves binary content and fresh CSRF',async()=>{
 const bytes=Uint8Array.from([0xff,0xd8,0,7,42,0xff,0xd9]);
 await server((req,res)=>{
  if(req.method==='POST'){
   assert.equal(req.headers['content-type'],'image/jpeg');
   assert.equal(req.headers['x-xsrf-token'],'current-csrf');
   const chunks=[];req.on('data',chunk=>chunks.push(chunk));req.on('end',()=>{
    assert.deepEqual(Buffer.concat(chunks),Buffer.from(bytes));
    res.setHeader('Content-Type','application/json');res.end('{"display_name":"Alex"}');
   });
  }else{res.setHeader('Content-Type','image/jpeg');res.end(bytes);}
 },async baseUrl=>{
  const client=new KoinonClient({transport:new FetchTransport({baseUrl,csrfToken:()=> 'current-csrf'})});
  assert.equal((await client.profile.uploadAvatar(new Blob([bytes],{type:'image/jpeg'}))).display_name,'Alex');
  assert.deepEqual(new Uint8Array(await (await client.profile.avatar()).arrayBuffer()),bytes);
 });
});
test('native problem and legacy envelope retain support reference and detail',async()=>{
 await server((req,res)=>{
  res.statusCode=403;res.setHeader('Content-Type','application/json');
  res.end(req.url.endsWith('/legacy')?JSON.stringify({error:{code:'ACCESS_DENIED',message:'Choose an authorized space',transaction_id:'native-legacy'}}):JSON.stringify({code:'ACCESS_DENIED',detail:'Choose an authorized space',transactionId:'native-problem'}));
 },async baseUrl=>{
  const transport=new FetchTransport({baseUrl});
  for(const [path,reference] of [['/legacy','native-legacy'],['/problem','native-problem']]){
   await assert.rejects(transport.request('GET',path),error=>error instanceof KoinonError&&error.code==='ACCESS_DENIED'&&error.message==='Choose an authorized space'&&error.requestId===reference);
  }
 });
});
test('catalog filters and recorded summaries survive the transport',async()=>{
 await server((req,res)=>{
  const query=new URL(req.url,'http://localhost').searchParams;
  assert.equal(query.get('format'),'pdf');assert.equal(query.get('tag'),'reviewed');assert.equal(query.get('sort'),'kind');
  res.setHeader('Content-Type','application/json');
  res.end(JSON.stringify({items:[],summaries:{entry:{format:'pdf',size_bytes:12,row_count:null,tags:['pdf','reviewed']}}}));
 },async baseUrl=>{
  const client=new KoinonClient({transport:new FetchTransport({baseUrl,accessToken:()=> 'caller-scoped'})});
  const page=await client.catalog.list('north',{format:'pdf',tag:'reviewed',sort:'kind'});
  assert.equal(page.summaries.entry.row_count,null);assert.equal(page.summaries.entry.size_bytes,12);
  assert.deepEqual(page.summaries.entry.tags,['pdf','reviewed']);
 });
});
test('folder moves keep observed parent and timestamp preconditions on the authenticated wire',async()=>{
 const input={parent_id:'destination',expected_parent_id:'original',expected_updated_at:'2026-11-01T08:00:00Z'};
 await server((req,res)=>{
  assert.equal(req.url,'/bff/api/v1/tenants/north%2Fdivision/catalog/folder%2Fone/move');
  assert.equal(req.method,'POST');assert.equal(req.headers.authorization,'Bearer editor');
  let raw='';req.on('data',part=>raw+=part);req.on('end',()=>{
   assert.deepEqual(JSON.parse(raw),input);
   res.setHeader('Content-Type','application/json');res.end(JSON.stringify({id:'folder/one',system_managed:false}));
  });
 },async baseUrl=>{
  const client=new KoinonClient({transport:new FetchTransport({baseUrl,accessToken:()=> 'editor'})});
  const moved=await client.catalog.move('north/division','folder/one',input);
  assert.equal(moved.system_managed,false);
 });
});
