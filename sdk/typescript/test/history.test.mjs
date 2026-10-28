// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {FetchTransport,KoinonClient} from '../dist/index.js';

test('history CRUD preserves revisions, explicit null, false and canonical filters',async()=>{
 const seen=[];const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://example.test/api/v1',accessToken:()=> 'fresh',fetch:async(url,init)=>{seen.push({url:new URL(url),init});return init.method==='DELETE'?new Response(null,{status:204}):new Response('{}',{headers:{'Content-Type':'application/json'}});}})});
 await client.chat.get('tenant/one','thread/one');
 await client.chat.update('tenant/one','thread/one',{expected_revision:2,folder_id:null,archived:false});
 await client.chat.suggestTitle('tenant/one','thread/one',{expected_revision:3,agent_id:'agent'});
 await client.chat.folders.create('tenant/one',{name:'Research',scope:{workspace_id:'w'}});
 await client.chat.folders.update('tenant/one','folder/one',{expected_revision:1,parent_id:null});
 await client.chat.folders.list('tenant/one',{query:{workspace_id:'w',page:2,page_size:5}});
 await client.chat.folders.delete('tenant/one','folder/one',2);
 await client.chat.threads('tenant/one',{query:{workspace_id:'w',project_id:'p',unfiled:true,status:'archived'}});
 assert.equal(seen[0].url.pathname,'/api/v1/tenants/tenant%2Fone/chat/threads/thread%2Fone');
 assert.deepEqual(JSON.parse(seen[1].init.body),{expected_revision:2,folder_id:null,archived:false});
 assert.deepEqual(JSON.parse(seen[4].init.body),{expected_revision:1,parent_id:null});
 assert.equal(seen[6].url.searchParams.get('expected_revision'),'2');
 assert.deepEqual(Object.fromEntries(seen[7].url.searchParams),{workspace_id:'w',project_id:'p',unfiled:'true',status:'archived'});
});
