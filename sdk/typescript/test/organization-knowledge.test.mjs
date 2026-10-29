// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {KoinonClient} from '../dist/index.js';
const fixtures=JSON.parse(readFileSync(new URL('../../contract/fixtures.json',import.meta.url))).fixtures;

test('organization knowledge API is deferred and uses complete tenant-only revision payloads',async()=>{
 assert.equal(typeof Object.getOwnPropertyDescriptor(KoinonClient.prototype,'organizationKnowledge')?.get,'function');
 const calls=[],policy=fixtures.OrganizationKnowledgeSettings;
 const client=new KoinonClient({transport:{request:async(method,path,options)=>{calls.push({method,path,options});return policy;}}});
 assert.equal(Object.hasOwn(client,'organizationKnowledge'),false);
 const options={headers:{'X-Test':'request-option'}};
 const current=await client.organizationKnowledge.get('north/one',options);
 assert.equal(current.capabilities.documents.rlm_model_role,'documents.rlm');
 assert.equal(current.capabilities.documents.rlm_recorded_views_required,true);
 assert.equal(current.capabilities.documents.rlm_recorded_views_reason,'RLM_DOCUMENT_VIEWS_REQUIRED');
 const input={expected_revision:current.revision,documents:{...current.documents,answer_mode:'rlm'},structured:current.structured};
 await client.organizationKnowledge.update('north/one',input,options);
 assert.deepEqual(calls.map(({method,path})=>[method,path]),[['GET','/tenants/north%2Fone/knowledge/settings'],['PUT','/tenants/north%2Fone/knowledge/settings']]);
 assert.deepEqual(calls[1].options.body,input);
 assert.equal(calls[0].options.query,undefined);
 assert.deepEqual(calls[0].options.headers,options.headers);
 assert.deepEqual(calls[1].options.headers,options.headers);
});

test('applied search, query, and audit snapshots preserve the captured policy',async()=>{
 const snapshot=fixtures.OrganizationKnowledgeSnapshot;
 const client=new KoinonClient({transport:{request:async()=>({knowledge_settings_snapshot:snapshot})}});
 for(const response of [await client.search('north',{question:'question'}),await client.query('north',{dataset_id:'dataset',question:'question'}),await client.chat.audit('north','run')]){
  assert.deepEqual(response.knowledge_settings_snapshot,snapshot);
 }
 const old=new KoinonClient({transport:{request:async()=>({run_id:'old',provenance_status:'not_recorded'})}});
 assert.equal((await old.chat.audit('north','old')).knowledge_settings_snapshot,undefined);
});
