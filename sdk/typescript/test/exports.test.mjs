// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {FetchTransport,KoinonClient} from '../dist/index.js';

test('export/share/evidence methods use actual HTTP, fresh auth and immutable binary bytes',async()=>{
 const calls=[];
 const server=createServer(async(req,res)=>{
  let body='';for await(const chunk of req)body+=chunk;
  calls.push({url:req.url,method:req.method,headers:req.headers,body:body?JSON.parse(body):undefined});
  if(req.url.endsWith('/download')){res.writeHead(200,{'Content-Type':'text/csv','Content-Disposition':'attachment; filename="result.csv"','ETag':'"immutable"'});res.end('9007199254740993,47\n');return;}
  if(req.method==='DELETE'){res.writeHead(204);res.end();return;}
  res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({items:[],total:0,page:2,page_size:10,pages:0}));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
  let count=0;const transport=new FetchTransport({baseUrl:`http://127.0.0.1:${server.address().port}/api/v1`,accessToken:()=>`fresh-${++count}`});
  const client=new KoinonClient({transport});
  await client.exports.review('north',{kind:'conversation',format:'markdown',thread_id:'thread',message_ids:['message'],include_evidence:false});
  await client.exports.review('north',{kind:'query_result',format:'csv',dataset_id:'dataset',query_id:'query',csv_mode:'exact'});
  await client.exports.create('north',{review_id:'review',expected_revision:'a'.repeat(64)});
  await client.exports.list('north',{query:{page:2,page_size:10,q:'renewal',status:'ready'}});
  await client.exports.get('north','export/one');
  const download=await client.exports.download('north','export/one');
  await client.exports.cancel('north','export/one');
  await client.shares.review('north',{thread_id:'thread',message_ids:['message']});
  await client.shares.create('north',{review_id:'review',expected_revision:'b'.repeat(64),expires_in_hours:1});
  await client.shares.list('north',{query:{page:2,status:'active'}});
  await client.shares.get('north','share/one');await client.shares.revoke('north','share/one');
  await client.evidence.conversation('north',{thread_id:'thread',message_ids:['message']});
  assert.equal(calls.length,13);assert.equal(count,13);
  assert.equal(calls[0].body.include_evidence,false);assert.equal(calls[0].body.kind,'conversation');assert.equal('root' in calls[0].body,false);
  assert.equal(calls[1].body.csv_mode,'exact');assert.match(calls[3].url,/page=2/);
  assert.match(calls[4].url,/export%2Fone$/);assert.match(calls[10].url,/share%2Fone$/);
  assert.equal(await download.blob.text(),'9007199254740993,47\n');assert.equal(download.filename,'result.csv');assert.equal(download.etag,'"immutable"');
  assert.deepEqual(calls.map(call=>call.headers.authorization),Array.from({length:13},(_,index)=>`Bearer fresh-${index+1}`));
 }finally{await new Promise(resolve=>server.close(resolve));}
});
