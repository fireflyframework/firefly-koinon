// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {FetchTransport,KoinonClient} from '../dist/index.js';

test('member pagination and invitation wire contracts preserve scope, null and fresh credentials',async()=>{
 const seen=[];let token=0;
 const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://example.test/api/v1',accessToken:()=>`fresh-${++token}`,fetch:async(url,init)=>{
  seen.push({url:new URL(url),init});return init.method==='DELETE'?new Response(null,{status:204}):new Response(JSON.stringify({items:[],actors:{},total:0,page:2,page_size:1,pages:0}),{headers:{'Content-Type':'application/json'}});
 }})});
 await client.members.list('tenant/one',{query:{q:'Málaga',role:'viewer',scope:'tenant',page:2,page_size:1}});
 await client.invitations.create('tenant/one',{role:'viewer',workspace_id:null,expires_in_hours:1});
 await client.invitations.list('tenant/one',{query:{status:'expired',page:2,page_size:1}});
 await client.invitations.inspect('not-logged-token');await client.invitations.redeem('not-logged-token');await client.invitations.revoke('tenant/one','invite/one');
 assert.deepEqual(Object.fromEntries(seen[0].url.searchParams),{q:'Málaga',role:'viewer',scope:'tenant',page:'2',page_size:'1'});
 assert.deepEqual(JSON.parse(seen[1].init.body),{role:'viewer',workspace_id:null,expires_in_hours:1});
 assert.equal(seen[3].url.pathname,'/api/v1/invitations/inspect');assert.deepEqual(JSON.parse(seen[3].init.body),{token:'not-logged-token'});
 assert.equal(seen[5].url.pathname,'/api/v1/tenants/tenant%2Fone/invitations/invite%2Fone');assert.equal(token,6);
});

test('audit dates and timezone are explicit wire values and scoped capabilities survive',async()=>{
 const seen=[];
 const client=new KoinonClient({transport:new FetchTransport({baseUrl:'https://example.test/api/v1',accessToken:()=> 'fresh',fetch:async(url)=>{
  seen.push(new URL(url));return new Response(JSON.stringify(url.endsWith('/context')?{subject:'issuer|user',workspace_permissions:{workspace:['catalog:read']}}:{items:[],actors:{},total:0,page:2,page_size:3,pages:0}),{headers:{'Content-Type':'application/json'}});
 }})});
 await client.audit.list('tenant/one',{query:{q:'Málaga',action:'catalog.updated',subject:'issuer|user',from_date:'2026-03-08',through_date:'2026-03-08',time_zone:'America/Los_Angeles',page:2,page_size:3,sort:'action',order:'asc'}});
 assert.deepEqual(Object.fromEntries(seen[0].searchParams),{q:'Málaga',action:'catalog.updated',subject:'issuer|user',from_date:'2026-03-08',through_date:'2026-03-08',time_zone:'America/Los_Angeles',page:'2',page_size:'3',sort:'action',order:'asc'});
 assert.deepEqual((await client.context()).workspace_permissions,{workspace:['catalog:read']});
});
