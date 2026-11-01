// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';import assert from 'node:assert/strict';import {KoinonClient} from '../dist/index.js';
test('optional chat retains synchronous stable groups, nested typed routes and caller options',async()=>{
 const calls=[];const transport={request:async(...args)=>{calls.push(args);return{id:'result'};},stream:async function*(){}};const client=new KoinonClient({transport});assert.equal(calls.length,0);assert.equal(client.chat,client.chat);assert.equal(typeof client.chat.attachments.get,'function');const signal=new AbortController().signal;
 await client.chat.folders.get('org/a','folder/b',{signal});await client.chat.attachments.upload('org/a','thread/b',new Blob(['owned']),'stable',{filename:'owned.txt',signal});
 assert.equal(calls[0][1],'/tenants/org%2Fa/chat/folders/folder%2Fb');assert.equal(calls[0][2].signal,signal);assert.equal(calls[1][2].headers['Idempotency-Key'],'stable');assert.equal(calls[1][2].body.get('file').name,'owned.txt');assert.throws(()=>client.chat.events('org','run',{lastEventId:'bad\nvalue'}),/Last-Event-ID/);assert.throws(()=>client.chat.attachments.upload('org','t',new Blob(['x']),'key'),/filename/);
});
test('optional chat streams close their owned iterator without retrying or canceling durable runs',async()=>{
 let calls=0,closed=0;const client=new KoinonClient({transport:{request:async()=>{throw Error('unexpected mutation');},stream:async function*(){calls++;try{yield{id:'1',type:'started',data:{}};yield{id:'2',type:'completed',data:{}};}finally{closed++;}}}});
 const events=client.chat.events('org','run',{lastEventId:'0'})[Symbol.asyncIterator]();assert.equal((await events.next()).value.id,'1');await events.return();assert.equal(closed,1);assert.equal(calls,1);
});
