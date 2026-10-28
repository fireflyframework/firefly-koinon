// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {FetchTransport,KoinonClient} from '../dist/index.js';

test('qualified glossary families preserve exact microseconds and canonical scope headers',async()=>{
 const calls=[],revision='2026-10-27T12:34:56.123456+00:00';
 const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://koinon.test/api/v1',accessToken:()=> 'fresh',fetch:async(url,init)=>{calls.push({url,...init});return init.method==='DELETE'?new Response(null,{status:204}):new Response(JSON.stringify({updated_at:revision}),{headers:{'Content-Type':'application/json'}});}})});
 for(const api of [client.structured.glossary,client.structured.agentGlossary]){
  const value=await api.create('north','workspace',{term:'Renewal',definition:'Original',synonyms:['Renew']});
  assert.equal(value.updated_at,revision);
  await api.update('north','workspace','term/one',{definition:null,tags:[]},value.updated_at);
  await api.remove('north','workspace','term/one',value.updated_at);
 }
 assert.equal(calls.length,6);
 calls.forEach((call,index)=>{assert.equal(call.headers.get('X-Tenant-ID'),'north');assert.equal(call.headers.get('X-Workspace-ID'),'workspace');assert.equal(call.url.includes('/agent/glossary'),index>=3);if(call.method!=='POST'){assert.equal(call.headers.get('If-Match'),'"'+revision+'"');assert.match(call.url,/term%2Fone$/);}});
 assert.deepEqual(JSON.parse(calls[1].body),{definition:null,tags:[]});
});
