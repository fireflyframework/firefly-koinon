// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {KoinonClient} from '../dist/index.js';

test('authorized applications use separate resources and escape connection identities',async()=>{
 const calls=[];
 const connection={id:'app/one',name:'Desktop client',workspace_name:'Research',scopes:['catalog:read'],status:'active'};
 const transport={request:async(method,path,options)=>{calls.push({method,path,options});return path.endsWith('/app%2Fone')?connection:{items:[connection],page:2,page_size:10,total:11,pages:2};}};
 const client=new KoinonClient({transport});
 const page=await client.authorizedApplications.list({query:{page:2,page_size:10,status:'active'}});
 assert.equal(page.page,2);
 assert.equal((await client.authorizedApplications.get('app/one')).workspace_name,'Research');
 await client.authorizedApplications.revoke('app/one');
 assert.deepEqual(calls.map(({method,path})=>[method,path]),[['GET','/authorized-applications'],['GET','/authorized-applications/app%2Fone'],['DELETE','/authorized-applications/app%2Fone']]);
 assert.deepEqual(calls[0].options.query,{page:2,page_size:10,status:'active'});
 assert.equal(calls[2].options.body,undefined);
});
