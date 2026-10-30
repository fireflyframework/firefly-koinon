// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import test from 'node:test';
import {KoinonClient} from '../dist/index.js';

test('immutable history helpers encode complete tuples and keep pagination explicit',async()=>{
 const calls=[];
 const client=new KoinonClient({transport:{request:async(method,path,options)=>{calls.push({method,path,options});return {source_part_id:'p/1',text:'retained'};}}});
 const part=await client.documents.part('t/1','d/1','v/1','e/1','p/1');
 await client.documents.versions('t/1','d/1',{page:2,page_size:5});
 await client.documents.version('t/1','d/1','v/1');
 await client.documents.extractions('t/1','d/1','v/1',{page:1,page_size:5});
 await client.documents.parts('t/1','d/1','v/1','e/1',{kind:'chunk',page:2,page_size:5});
 await client.documents.versionOriginal('t/1','d/1','v/1');
 assert.equal(part.source_part_id,'p/1');
 assert.equal(calls[0].path,'/tenants/t%2F1/documents/d%2F1/versions/v%2F1/extractions/e%2F1/parts/p%2F1');
 assert.deepEqual(calls[1].options.query,{page:2,page_size:5});
 assert.equal(calls[2].path,'/tenants/t%2F1/documents/d%2F1/versions/v%2F1');
 assert.equal(calls[3].path.endsWith('/versions/v%2F1/extractions'),true);
 assert.deepEqual(calls[4].options.query,{kind:'chunk',page:2,page_size:5});
 assert.equal(calls[5].options.responseType,'download');
});
