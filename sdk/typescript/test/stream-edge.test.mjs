// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createServer} from 'node:http';
import {FetchTransport} from '../dist/index.js';
const collect=async transport=>{const rows=[];for await(const row of transport.stream('GET','/events'))rows.push(row);return rows;};
function stream(frame,fragment=false){const bytes=new TextEncoder().encode(frame);return new FetchTransport({baseUrl:'https://example.test',fetch:async()=>new Response(new ReadableStream({start(controller){if(fragment)for(const byte of bytes)controller.enqueue(Uint8Array.of(byte));else controller.enqueue(bytes);controller.close();}}),{headers:{'Content-Type':'text/event-stream'}})});}
test('SSE BOM splitCRLF splitUTF8 multiline persistentID NUL and incompleteEOF parity',async()=>{
 const rows=await collect(stream('\ufeffid: 7\r\nevent:\r\ndata: {"text":\r\ndata: "café"}\r\n\r\nid: bad\0id\ndata: {}\n\ndata: {"text":"unfinished"}',true));
 assert.deepEqual(rows,[{id:'7',type:'message',data:{text:'café'}},{id:'7',type:'message',data:{}}]);
});
test('SSE emptyJSON and UTF8 byte budget fail without reconnect',async()=>{
 await assert.rejects(collect(stream('data:\n\n')),SyntaxError);
 await assert.rejects(collect(stream('data: {"text":"'+'é'.repeat(524288)+'"}\n\n')),/exceeds 1 MiB/);
});
test('realHTTP early iterator close releases response without canceling a durable job',async()=>{
 let closed;const disconnected=new Promise(resolve=>{closed=resolve;});let requests=0;
 const app=createServer((request,response)=>{requests++;response.writeHead(200,{'Content-Type':'text/event-stream'});response.write('id: 1\ndata: {"text":"started"}\n\n');response.on('close',closed);});
 await new Promise(resolve=>app.listen(0,'127.0.0.1',resolve));
 try{
  const transport=new FetchTransport({baseUrl:`http://127.0.0.1:${app.address().port}`,accessToken:()=> 'fresh'});
  const events=transport.stream('GET','/events')[Symbol.asyncIterator]();
  assert.equal((await events.next()).value.id,'1');
  await events.return();
  let timer;try{await Promise.race([disconnected,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('response remained open')),2000);})]);}finally{clearTimeout(timer);}
  assert.equal(requests,1);
 }finally{app.closeAllConnections();await new Promise(resolve=>app.close(resolve));}
});
