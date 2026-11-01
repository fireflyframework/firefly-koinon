// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import test from 'node:test';
import { createAvailabilityApi } from '../dist/availability.js';

test('availability factory preserves exact scoped input, cancellation and independent serving/attempt states', async()=>{
 const calls=[];
 const result={observed_at:'2026-11-01T00:00:00Z',items:{asset:{phase:'failed',revision:{source_version_id:'old'},latest_attempt:{id:'new',state:'failed'},read:{state:'ready'},search:{state:'pending'}}}};
 const api=createAvailabilityApi({request:async(...args)=>{calls.push(args);return result;}});
 const controller=new AbortController();const options={signal:controller.signal,headers:{'X-Request':'retained'}};
 const input={asset_ids:['asset'],workspace_id:'space'};
 const response=await api.observe('north/office',input,options);
 await api.processing('north/office',{page:2,page_size:1},options);
 assert.equal(response.items.asset.revision.source_version_id,'old');
 assert.equal(response.items.asset.latest_attempt.state,'failed');
 assert.equal(response.items.asset.read.state,'ready');
 assert.equal(calls[0][1],'/tenants/north%2Foffice/catalog/availability');
 assert.equal(calls[0][2].body,input);
 assert.ok(calls.every(call=>call[2].signal===controller.signal));
 assert.equal(calls[1][1],'/tenants/north%2Foffice/knowledge-processing');
 assert.equal(options.headers['X-Request'],'retained');
});
