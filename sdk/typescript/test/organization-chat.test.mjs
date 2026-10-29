// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {KoinonClient} from '../dist/index.js';

test('organization default preserves clear, revision, and explicit scope filters',async()=>{
 const calls=[];
 const client=new KoinonClient({transport:{request:async(method,path,options)=>{
  calls.push({method,path,options});return {tenant_id:'north/one',default_agent_id:null,revision:2,configured:false,can_run:false,status:'unconfigured'};
 }}});
 assert.equal((await client.organizationChat.get('north/one',{workspace_id:'w',project_id:'p'})).status,'unconfigured');
 await client.organizationChat.update('north/one',{default_agent_id:null,expected_revision:1});
 assert.deepEqual(calls.map(({method,path})=>[method,path]),[['GET','/tenants/north%2Fone/chat/settings'],['PUT','/tenants/north%2Fone/chat/settings']]);
 assert.deepEqual(calls[0].options.query,{workspace_id:'w',project_id:'p'});
 assert.deepEqual(calls[1].options.body,{default_agent_id:null,expected_revision:1});
});
