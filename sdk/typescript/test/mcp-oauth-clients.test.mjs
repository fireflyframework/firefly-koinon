// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {KoinonClient} from '../dist/index.js';

test('organization OAuth operations preserve tenant paths, options, filters and exact decisions',async()=>{
 const calls=[],value={id:'row/one',client_id:'owned',revision:2};
 const options={signal:new AbortController().signal,headers:{'X-Owned':'yes'}};
 const client=new KoinonClient({transport:{request:async(method,path,request)=>{calls.push({method,path,request});return path.endsWith('/rotate-secret')?{client:value,client_secret:'owned-once'}:value;}}});
 assert.ok(client.mcpOAuthClients,'The SDK must expose organization OAuth registrations');
 await client.mcp.connection(options);
 await client.mcp.organizationConnection('north/team',options);
 await client.mcpOAuthClients.readiness('north/team',options);
 await client.mcpOAuthClients.list('north/team',{...options,query:{q:'Research',status:'enabled',page:2,page_size:10,sort:'updated_at',order:'desc'}});
 await client.mcpOAuthClients.create('north/team',{name:'Research',client_type:'public',redirect_uris:['https://client.example/callback'],scopes:['catalog:read']},options);
 await client.mcpOAuthClients.get('north/team','row/one',options);
 await client.mcpOAuthClients.update('north/team','row/one',{expected_revision:1,enabled:false},options);
 const rotated=await client.mcpOAuthClients.rotateSecret('north/team','row/one',{expected_revision:2},options);
 assert.equal(rotated.client_secret,'owned-once');
 const prefix='/tenants/north%2Fteam/mcp';
 assert.deepEqual(calls.map(({method,path})=>[method,path]),[
  ['GET','/mcp/connection'],['GET',prefix+'/connection'],
  ['GET',prefix+'/oauth-clients/readiness'],['GET',prefix+'/oauth-clients'],
  ['POST',prefix+'/oauth-clients'],['GET',prefix+'/oauth-clients/row%2Fone'],
  ['PATCH',prefix+'/oauth-clients/row%2Fone'],['POST',prefix+'/oauth-clients/row%2Fone/rotate-secret'],
 ]);
 assert.deepEqual(calls[3].request.query,{q:'Research',status:'enabled',page:2,page_size:10,sort:'updated_at',order:'desc'});
 assert.deepEqual(calls[6].request.body,{expected_revision:1,enabled:false});
 assert.deepEqual(calls[7].request.body,{expected_revision:2});
 assert.ok(calls.every(({request})=>request.signal===options.signal&&request.headers['X-Owned']==='yes'));
});
