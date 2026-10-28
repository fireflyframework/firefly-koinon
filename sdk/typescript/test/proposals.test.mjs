// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {KoinonClient} from '../dist/index.js';

test('proposal helpers preserve explicit confirmation and never auto-confirm evidence',async()=>{
 const calls=[];const client=new KoinonClient({transport:{request:async(method,path,options={})=>{calls.push({method,path,...options});return {};}}});
 await client.chat.proposals.get('north','run/one','proposal/one');
 assert.equal(calls.length,1);assert.equal(calls[0].method,'GET');
 await client.chat.proposals.confirm('north','run/one','proposal/one',{confirm:true,expected_revision:1});
 await client.chat.proposals.cancel('north','run/one','proposal/one',{expected_revision:1});
 assert.equal(calls[0].path,'/tenants/north/chat/runs/run%2Fone/proposals/proposal%2Fone');
 assert.deepEqual(calls[1].body,{confirm:true,expected_revision:1});assert.deepEqual(calls[2].body,{expected_revision:1});
});
