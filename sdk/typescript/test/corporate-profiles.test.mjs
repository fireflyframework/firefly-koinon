// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import test from 'node:test';
import {KoinonClient} from '../dist/index.js';

test('corporate profile controls preserve tenant scope, partial preferences and refresh admission',async()=>{
 const calls=[];
 const transport={request:async(method,path,options={})=>{calls.push({method,path,options});return {tenant_id:'north',status:'queued'};}};
 const api=new KoinonClient({transport}).corporateProfiles;
 const controller=new AbortController();
 const options={signal:controller.signal};
 await api.presentation('north/office',{workspace_id:'shared'},options);
 await api.updatePresentation('north/office',{expected_revision:3,avatar_mode:'personal'},{workspace_id:'shared'},options);
 await api.refreshSelf('north/office',{}, {workspace_id:'shared'},options);
 await api.refreshPerson('north/office','person/one',{}, {},options);
 assert.equal(calls.length,4);
 assert.deepEqual(calls.map(call=>call.method),['GET','PATCH','POST','POST']);
 assert.equal(calls[0].path,'/tenants/north%2Foffice/organization/people/me/presentation');
 assert.deepEqual(calls[1].options.body,{expected_revision:3,avatar_mode:'personal'});
 assert.deepEqual(calls[2].options.query,{workspace_id:'shared'});
 assert.deepEqual(calls[2].options.body,{});
 assert.deepEqual(calls[3].options.body,{});
 assert.equal(calls[3].path,'/tenants/north%2Foffice/organization/people/person%2Fone/profile-refresh');
 assert.ok(calls.every(call=>call.options.signal===controller.signal));
});
