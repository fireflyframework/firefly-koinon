// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {FetchTransport,KoinonClient} from '../dist/index.js';

test('owner audit preserves private used receipt and unknown completeness',async()=>{
 const calls=[];
 const value={run_id:'run/one',provenance_status:'recorded',source_provenance_complete:true,
 private_files:[{id:'file',filename:'Notes.md',media_type:'text/markdown',sha256:'a'.repeat(64),used_revision:1,availability:'expired'}]};
 const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://koinon.test/api/v1',accessToken:()=> 'fresh',fetch:async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});}})});
 const audit=await client.chat.audit('north','run/one');
 assert.equal(audit.private_files[0].used_revision,1);
 assert.equal(audit.private_files[0].availability,'expired');
 assert.ok(calls[0].url.endsWith('/chat/runs/run%2Fone/audit'));
 assert.equal(calls[0].init.headers.get('Authorization'),'Bearer fresh');
});

test('audit execution database and imported snapshots preserve server observations',async()=>{
 const value={run_id:'run',provenance_status:'recorded',source_provenance_complete:true,
 sql_attempts:[{result_id:'result',ordinal:1,stage:'execution',statement_sha256:'b'.repeat(64),
 outcome:'succeeded',executed:true,snapshot_pins:{Ledger:'snapshot'},engine:'duckdb',
 database:'memory',catalog:'memory',schema:'main',execution_kind:'imported_snapshot',
 dataset_id:'asset',native_dataset_id:'native-asset',tables:[{table_id:'table',table_name:'Ledger',snapshot_id:'snapshot'}]}],
 native_reads:[{result_id:'result',stage:'retrieval',domain:'documents',tenant_id:'north',
 workspace_id:'workspace',entity_id:'document',content_sha256:'c'.repeat(64),origin:null,engine:null}]};
 const client=new KoinonClient({transport:{request:async()=>value}});
 const audit=await client.chat.audit('north','run');
 assert.equal(audit.sql_attempts[0].database,'memory');assert.equal(audit.sql_attempts[0].schema,'main');
 assert.equal(audit.sql_attempts[0].tables[0].snapshot_id,'snapshot');
 assert.equal(audit.native_reads[0].origin,null);assert.equal(audit.native_reads[0].engine,null);
});

test('audit preserves exact optional answer publication pins without backfilling old replies',async()=>{
 const release={version:1,policy_version:'knowledge-only-v1',run_id:'run',message_id:'answer',tenant_id:'north',generation_id:'generation',publication_sequence:7,outcome:'grounded',text_sha256:'a'.repeat(64),citations_sha256:'b'.repeat(64),artifacts_sha256:'c'.repeat(64),policy_sha256:'d'.repeat(64),fact_ids:['fact'],result_pins:[{id:'result',sha256:'e'.repeat(64)}],source_refs:[{id:'reference',asset_id:'document',kind:'document',title:'Fact'}],created_at:'2026-11-01T19:00:00.123456Z'};
 const client=new KoinonClient({transport:{request:async()=>({run_id:'run',provenance_status:'recorded',output_release:release})}});
 const audit=await client.chat.audit('north','run');
 assert.deepEqual(audit.output_release,release);
 assert.equal(audit.output_release.publication_sequence,7);
 assert.equal(audit.output_release.result_pins[0].id,'result');
 assert.equal(audit.output_release.source_refs[0].asset_id,'document');
 const oldClient=new KoinonClient({transport:{request:async()=>({run_id:'old',provenance_status:'not_recorded'})}});
 assert.equal((await oldClient.chat.audit('north','old')).output_release,undefined);
});
