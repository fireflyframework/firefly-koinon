// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {KoinonClient} from '../dist/index.js';

test('connection methods preserve required nullable preconditions and revision/idempotency headers',async()=>{
 const calls=[];const client=new KoinonClient({transport:{request:async(method,path,options={})=>{calls.push({method,path,...options});return {};}}});
 await client.knowledgeIndexes.list('north',{workspace_id:'workspace',domain:'documents',offset:50,limit:25});
 await client.knowledgeIndexes.create('north',{workspace_id:'workspace',domain:'documents',provider_id:'provider',model_id:'embed',expected_active_id:null,expected_connection_revision:null,batch_size:1},'once');
 await client.knowledgeIndexes.resume('north','index/one',{expected_revision:2},'resume');
 assert.equal(calls[0].query.offset,50);assert.equal(calls[1].body.expected_active_id,null);assert.equal(calls[1].headers['Idempotency-Key'],'once');
 assert.equal(calls[2].path,'/tenants/north/knowledge-indexes/index%2Fone/resume');
 await client.identity.update('north','provider',{expected_revision:3,credential:null});
 assert.deepEqual(calls[3].body,{expected_revision:3,credential:null});
 await client.identity.update('north','provider',{expected_revision:4,name:'Renamed'});
 assert.equal('credential' in calls[4].body,false);
 await client.identity.groups('north','provider',{query:{after:'opaque cursor',limit:10}});
 assert.equal(calls[5].query.after,'opaque cursor');
 await client.identity.removeMapping('north','provider','mapping',7);
 assert.equal(calls[6].query.expected_revision,7);
 await client.identity.testStatus('north','provider','test/id');
 assert.equal(calls[7].path,'/tenants/north/identity/providers/provider/tests/test%2Fid');
});

test('agent protocol choice preserves explicit null and omission without adding request flags',async()=>{
 const bodies=[];const client=new KoinonClient({transport:{request:async(method,path,options={})=>{bodies.push(options.body);return {};}}});
 for(const output_mode of ['default','native',null])
  await client.agents.update('north','agent',{model_options:{max_tokens:512,output_mode}});
 await client.agents.update('north','agent',{name:'Unchanged protocol'});
 assert.deepEqual(bodies.slice(0,3).map(x=>x.model_options.output_mode),['default','native',null]);
 assert.equal('model_options' in bodies[3],false);
 assert.equal(bodies.some(x=>'extra_body' in x),false);
});
