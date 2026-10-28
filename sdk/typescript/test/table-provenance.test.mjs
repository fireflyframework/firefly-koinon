// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {KoinonClient,FetchTransport} from '../dist/index.js';

test('exact used snapshot and native server history page survive transport',async()=>{
 const calls=[];
 const unknown={dataset_id:'dataset',table_id:'table',native_dataset_id:'native-data',native_table_id:'native-table',snapshot_id:'old/snapshot',status:'not_recorded',snapshot_status:'READY',level:'file_section'};
 const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://koinon.test/api/v1',accessToken:()=> 'fresh',fetch:async(url,init)=>{calls.push({url,init});const value=new URL(url).pathname.endsWith('/provenance')?unknown:{items:[unknown],total:3,page:2,page_size:1,pages:3,has_next:true,has_previous:true,current_snapshot_id:'new-snapshot'};return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});}})});
 const used=await client.dataset.tableProvenance('north','data/set','table/one','old/snapshot');
 const page=await client.dataset.tableSnapshots('north','data/set','table/one',{query:{page:2,page_size:1}});
 assert.equal(used.snapshot_id,'old/snapshot');assert.equal(used.status,'not_recorded');
 assert.equal(page.current_snapshot_id,'new-snapshot');assert.equal(page.total,3);
 assert.equal(new URL(calls[0].url).searchParams.get('snapshot_id'),'old/snapshot');
 assert.ok(calls[0].url.includes('data%2Fset/tables/table%2Fone'));
 assert.equal(calls[0].init.headers.get('Authorization'),'Bearer fresh');
 assert.equal(new URL(calls[1].url).searchParams.get('page'),'2');
});
