// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {KoinonClient} from '../dist/index.js';

test('branding defaults and tenant writes preserve revision, explicit null, and request options',async()=>{
 const calls=[],branding={product_name:'Example',logo_light:null,font_family:'Manrope'};
 const client=new KoinonClient({transport:{request:async(method,path,options)=>{calls.push({method,path,options});return path==='/branding/defaults'?branding:{tenant_id:'north/one',revision:2,origin:'organization',branding};}}});
 const options={headers:{'X-Test':'options'}};
 assert.equal((await client.branding.defaults(options)).product_name,'Example');
 assert.equal((await client.branding.get('north/one',options)).revision,2);
 await client.branding.update('north/one',{expected_revision:1,branding},options);
 await client.branding.reset('north/one',{expected_revision:2},options);
 assert.deepEqual(calls.map(({method,path})=>[method,path]),[['GET','/branding/defaults'],['GET','/tenants/north%2Fone/branding'],['PUT','/tenants/north%2Fone/branding'],['POST','/tenants/north%2Fone/branding/reset']]);
 assert.deepEqual(calls[2].options.body,{expected_revision:1,branding});
 assert.deepEqual(calls[3].options.body,{expected_revision:2});
 assert.ok(calls.every(x=>x.options.headers===options.headers));
});
