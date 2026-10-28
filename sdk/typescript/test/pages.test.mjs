// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {offsetPages,cursorPages} from '../dist/index.js';
test('pagination is lazy, no prefetch or client slicing, items-only once',async()=>{
 const calls=[];const pages=offsetPages(async page=>{calls.push(page);return {items:[page],page,pages:3};});
 assert.deepEqual(calls,[]);assert.deepEqual((await pages.next()).value.items,[1]);await pages.return();assert.deepEqual(calls,[1]);
 const rows=[];for await(const page of offsetPages(async()=>({items:[42]})))rows.push(page);assert.equal(rows.length,1);
});
test('pagination guards ignored pages and repeated cursors, passes cancellation',async()=>{
 await assert.rejects(async()=>{for await(const page of offsetPages(async()=>({items:[1],page:1,pages:3})))void page;},/page/);
 const seen=[];for await(const page of cursorPages(async cursor=>{seen.push(cursor);return {items:[1],next_cursor:cursor===undefined?'next':null};}))void page;
 assert.deepEqual(seen,[undefined,'next']);
 await assert.rejects(async()=>{for await(const page of cursorPages(async()=>({items:[1],next_cursor:'same'})))void page;},/cursor/);
 const abort=new AbortController();abort.abort();let calls=0;await assert.rejects(async()=>{for await(const page of offsetPages(async()=>{calls++;return {items:[]};},1,abort.signal))void page;});assert.equal(calls,0);
});
