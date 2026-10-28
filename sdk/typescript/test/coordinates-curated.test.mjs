// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {KoinonClient,FetchTransport} from '../dist/index.js';

test('typed coordinates retain exact snapshot/zero cells and consent remains pending through FetchTransport',async()=>{
 const calls=[];
 const manifest={dataset_id:'dataset',table_id:'table',native_dataset_id:'native',native_table_id:'native-table',snapshot_id:'used/old',status:'partial',index_base:0,parser_decisions:[{name:'header',value:false}],dependencies:[{name:'reader',version:'1'}]};
 const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://koinon.test/api/v1',accessToken:()=> 'fresh',fetch:async(url,init)=>{calls.push({url,init});const value=url.includes('/confirm')?{status:'pending',operation_id:'intent',intent_id:'intent',reason:'commit_outcome_unresolved'}:url.endsWith('/cells')?{manifest,items:[{output_row:0,output_column:0,source_row:7,source_column:0,source_path:['Actuals',0],header_cells:[{row:0,column:0}],source_type:'decimal'}]}:manifest;return new Response(JSON.stringify(value),{status:url.includes('/confirm')?202:200,headers:{'Content-Type':'application/json'}});}})});
 const observed=await client.dataset.tableCoordinates('north','data/set','table','used/old');
 assert.equal(observed.parser_decisions[0].value,false);
 const cells=await client.dataset.tableCoordinateCells('north','data/set','table',{snapshot_id:'used/old',cells:[{row:0,column:0}]});
 assert.deepEqual(cells.items[0].header_cells,[{row:0,column:0}]);
 const outcome=await client.knowledgeIntents.confirm('north','intent',{confirm:true,expected_revision:1,authorization_digest:'a'.repeat(64)},'exact-consent');
 assert.equal(outcome.status,'pending');assert.equal(calls.length,3);
 assert.equal(new URL(calls[0].url).searchParams.get('snapshot_id'),'used/old');
 assert.deepEqual(JSON.parse(calls[1].init.body).cells,[{row:0,column:0}]);
 assert.equal(calls[2].init.headers.get('Idempotency-Key'),'exact-consent');
 assert.equal(JSON.parse(calls[2].init.body).confirm,true);
});

test('document revision is a pair distinct from raw If-Match and malformed pairs never send',async()=>{
 const calls=[];
 const client=new KoinonClient({transport:{request:async(method,path,options)=>{calls.push({method,path,options});return {};}}});
 const version='12345678-1234-1234-1234-123456789abc',extraction='abcdef01-1234-1234-1234-123456789abc';
 await client.documents.reingest('north','doc',{expected_sha256:'raw-sha',expected_source_version_id:version,expected_extraction_id:extraction});
 assert.equal(calls[0].options.headers['If-Match'],'"raw-sha"');
 assert.equal(calls[0].options.headers['X-Koinon-Source-Version'],version);
 assert.equal(calls[0].options.headers['X-Koinon-Extraction'],extraction);
 assert.throws(()=>client.documents.reingest('north','doc',{expected_sha256:'raw-sha',expected_source_version_id:version}),/together/);
 assert.equal(calls.length,1);
});
