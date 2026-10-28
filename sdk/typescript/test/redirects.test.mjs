// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {FetchTransport} from '../dist/index.js';

test('redirect rejection prevents POST credential bodies reaching another origin',async()=>{
 let reached=0;
 const sink=createServer(async(req,res)=>{reached++;for await(const _ of req){}res.writeHead(200,{'Content-Type':'application/json'});res.end('{}');});
 await new Promise(resolve=>sink.listen(0,'127.0.0.1',resolve));
 const source=createServer((req,res)=>{res.writeHead(307,{Location:`http://127.0.0.1:${sink.address().port}/collect`});res.end();});
 await new Promise(resolve=>source.listen(0,'127.0.0.1',resolve));
 try{
  const transport=new FetchTransport({baseUrl:`http://127.0.0.1:${source.address().port}/api/v1`,accessToken:()=> 'controlled-caller-bearer'});
  await assert.rejects(()=>transport.request('POST','/providers',{body:{secret:'controlled-provider-secret'}}));
  assert.equal(reached,0);
 }finally{await Promise.all([new Promise(resolve=>source.close(resolve)),new Promise(resolve=>sink.close(resolve))]);}
});
