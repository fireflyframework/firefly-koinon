// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {FetchTransport,KoinonClient} from '../dist/index.js';

test('connection and external review methods preserve typed contracts and never invent approval',async()=>{
 const fixtures=JSON.parse(await readFile(new URL('../../contract/fixtures.json',import.meta.url),'utf8')).fixtures;
 const seen=[];
 const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://organization.example/api/v1',accessToken:()=> 'owned-test',fetch:async(url,init)=>{
  const path=new URL(url).pathname;const body=init.body?JSON.parse(init.body):null;
  seen.push({method:init.method,path,key:init.headers.get('Idempotency-Key'),body});
  let value;
  if(path.endsWith('/mcp/connection'))value=fixtures.McpConnectionDescriptor;
  else if(path.includes('/external-file-reviews'))value={...fixtures.ExternalFileReviewView,...(path.endsWith('/approve')?{status:'unresolved',receipt:null,source_id:null}:{})};
  else if(path.endsWith('/approve'))value=fixtures.PendingKnowledgeCommit;
  else value=fixtures.ExternalReviewView;
  return new Response(JSON.stringify(value),{status:path.endsWith('/approve')?202:200});
 }})});
 const descriptor=await client.mcp.connection();assert.equal(descriptor.review.external_redirect,false);
 const decision={expected_revision:1,authorization_digest:'a'.repeat(64),nonce:'n'.repeat(43)};
 const proposal={action:'create_draft',destination_id:'owned-collection',content:{title:'Proposed',body:'External proposed text.'}};
 await client.externalReviews.stage('north/team',proposal,'text-stage');
 await client.externalReviews.get('north/team','review/one');
 const pending=await client.externalReviews.approve('north/team','review/one',decision,'text-approval');
 await client.externalReviews.cancel('north/team','review/one',decision);
 const file={filename:'owned.txt',mode:'document',destination_id:'owned-collection',size_bytes:3,sha256:'b'.repeat(64)};
 const chunk={index:0,data_base64:'YWJj',sha256:'b'.repeat(64)};
 await client.externalFileReviews.stage('north/team',file,'file-stage');
 await client.externalFileReviews.get('north/team','file/one');
 await client.externalFileReviews.chunk('north/team','file/one',chunk);
 await client.externalFileReviews.seal('north/team','file/one');
 const unresolved=await client.externalFileReviews.approve('north/team','file/one',decision,'file-approval');
 await client.externalFileReviews.cancel('north/team','file/one',decision);
 assert.equal(pending.status,'pending');assert.equal(unresolved.status,'unresolved');assert.equal(unresolved.receipt,null);
 assert.equal(seen.length,11);assert.deepEqual(seen.map(r=>r.key),[null,'text-stage',null,'text-approval',null,'file-stage',null,null,null,'file-approval',null]);
 assert.deepEqual(seen[1].body,proposal);assert.deepEqual(seen[3].body,decision);assert.deepEqual(seen[7].body,chunk);
 assert.equal(seen[2].path,'/api/v1/tenants/north%2Fteam/external-knowledge-reviews/review%2Fone');
 assert.equal(typeof client.externalReviews.challenge,'undefined');
});
