// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import test from 'node:test';
import {KoinonClient} from '../dist/index.js';

test('activity retains time-zone windows, unknown measurements and cancellation',async()=>{
 const calls=[];
 const response={mcp:{requests:{value:null,status:'unavailable'}},coverage:{missing_observations:null}};
 const transport={request:async(method,path,options)=>{calls.push({method,path,options});return response;}};
 const client=new KoinonClient({transport});
 const window={start_at:'2026-10-01T00:00:00Z',end_at:'2026-11-01T00:00:00Z',time_zone:'Europe/Madrid'};
 const controller=new AbortController();
 const options={signal:controller.signal};
 const personal=await client.activity.personal('north/office',window,options);
 await client.activity.administrative('north/office',window,options);
 assert.equal(personal.mcp.requests.value,null);
 assert.equal(personal.coverage.missing_observations,null);
 assert.deepEqual(calls.map(call=>[call.method,call.path]),[['POST','/tenants/north%2Foffice/activity/personal'],['POST','/tenants/north%2Foffice/activity/administration']]);
 assert.ok(calls.every(call=>call.options.body===window&&call.options.signal===controller.signal));
 assert.deepEqual(options,{signal:controller.signal});
});
