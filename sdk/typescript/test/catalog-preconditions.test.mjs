// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import test from 'node:test';
import {KoinonClient} from '../dist/index.js';

test('catalog lifecycle preserves existing options and exact timestamp preconditions', async()=>{
 const calls=[];
 const transport={request:async(...args)=>{calls.push(args);return {};}};
 const api=new KoinonClient({transport});
 const stamp='2026-11-01T15:01:02.123456Z';
 await api.catalog.archive('north','item');
 await api.catalog.archive('north','item',{expected_updated_at:stamp,headers:{'X-Test':'kept'}});
 await api.catalog.restore('north','item',{expected_updated_at:stamp});
 await api.catalog.update('north','item',{name:'Updated',expected_updated_at:stamp});
 assert.deepEqual(calls[0][2].query,{});
 assert.equal(calls[1][2].query.expected_updated_at,stamp);
 assert.equal(calls[1][2].headers['X-Test'],'kept');
 assert.equal(calls[2][2].query.expected_updated_at,stamp);
 assert.equal(calls[3][2].body.expected_updated_at,stamp);
 assert.ok(calls.every(([, , options])=> !('expected_updated_at' in options)));
});
