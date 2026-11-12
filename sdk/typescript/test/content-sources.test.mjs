// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';

test('source helpers preserve owner paths and revision, stripping unknown request fields',async()=>{
 const module=await import('../dist/content-sources.js').catch(()=>({}));
 assert.equal(typeof module.createContentSourcesApi,'function');
 const calls=[];
 const api=module.createContentSourcesApi({request:async(...args)=>{calls.push(args);return {items:[],next_cursor:null};}});
 await api.list('north/office',{cursor:'opaque',limit:2,secret:'NO'});
 await api.children('north/office','c/id',{drive_id:'drive',folder_id:'folder',cursor:'next',secret:'NO'});
 await api.disconnect('north/office','c/id',{expected_revision:3,access_token:'NO'});
 assert.equal(calls[0][1],'/tenants/north%2Foffice/content-sources/connections');
 assert.deepEqual(calls[0][2].query,{cursor:'opaque',limit:2});
 assert.equal(calls[1][1],'/tenants/north%2Foffice/content-sources/connections/c%2Fid/children');
 assert.deepEqual(calls[1][2].query,{drive_id:'drive',folder_id:'folder',cursor:'next'});
 assert.deepEqual(calls[2][2].body,{expected_revision:3});
 assert.equal(api.begin,undefined);
});
