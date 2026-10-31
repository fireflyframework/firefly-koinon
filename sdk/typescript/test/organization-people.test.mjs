// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import test from 'node:test';
import {KoinonClient} from '../dist/index.js';

test('organization directory helpers preserve tenant identities, revisions, filters and cancellation',async()=>{
 const calls=[];
 const transport={request:async(method,path,options={})=>{calls.push({method,path,options});return {id:null,display_name:'Alex Morgan',revision:0};}};
 const api=new KoinonClient({transport}).organizationPeople;
 const controller=new AbortController();
 const options={signal:controller.signal};
 const self=await api.me('north/office',{workspace_id:'shared'},options);
 await api.list('north/office',{q:'Alex',unassigned:false,page:2,page_size:10},options);
 await api.create('north/office',{profile_id:'profile',job_title:'Engineer'},options);
 await api.get('north/office','person/one',{workspace_id:'shared'},options);
 await api.update('north/office','person/one',{expected_revision:4,manager_id:null},options);
 await api.avatar('north/office','person/one',{workspace_id:'shared'},options);
 await api.reports('north/office','person/one',{workspace_id:'shared',page:2},options);
 await api.units('north/office',{parent_id:'department',page_size:10},options);
 await api.createUnit('north/office',{name:'Engineering',kind:'department'},options);
 await api.updateUnit('north/office','unit/one',{expected_revision:3,parent_id:null},options);
 await api.deleteUnit('north/office','unit/one',3,options);
 await api.settings('north/office',options);
 await api.updateSettings('north/office',{expected_revision:0,visibility:'shared_workspaces'},options);
 await api.mapping('north/office','provider/one',options);
 await api.updateMapping('north/office','provider/one',{expected_revision:0,enabled:true,fields:{job_title:'job_title'}},options);
 assert.equal(self.id,null);
 assert.equal(calls.length,15);
 assert.equal(calls[0].path,'/tenants/north%2Foffice/organization/people/me');
 assert.deepEqual(calls[1].options.query,{q:'Alex',unassigned:false,page:2,page_size:10});
 assert.deepEqual(calls[4].options.body,{expected_revision:4,manager_id:null});
 assert.equal(calls[5].path,'/tenants/north%2Foffice/organization/people/person%2Fone/avatar');
 assert.equal(calls[5].options.responseType,'download');
 assert.equal(calls[9].path,'/tenants/north%2Foffice/organization/units/unit%2Fone');
 assert.deepEqual(calls[10].options.query,{expected_revision:3});
 assert.equal(calls[13].path,'/tenants/north%2Foffice/organization/profile-mappings/provider%2Fone');
 assert.equal(calls[14].method,'PUT');
 assert.ok(calls.every(call=>call.options.signal===controller.signal));
 assert.deepEqual(options,{signal:controller.signal});
});
