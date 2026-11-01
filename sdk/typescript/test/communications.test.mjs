// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {createCommunicationsApi} from '../dist/communications.js';
const invitation='4d2d21dd-bd63-44a0-9afb-205b38209bf4';
function fixture(){const calls=[];return {calls,api:createCommunicationsApi({request:async(...args)=>{calls.push(args);return {};},stream:async function*(){}})};}
test('recipient and delivery filters stay encoded and server paginated',async()=>{
 const {api,calls}=fixture();await api.recipients.list('a/b',{q:'Alex',limit:20,after:'cursor'});
 await api.administration.deliveries('a/b',{page:2,page_size:25,created_from:'2026-10-01T00:00:00Z'});
 assert.equal(calls[0][1],'/tenants/a%2Fb/communications/recipients');assert.equal(calls[0][2].query.after,'cursor');assert.equal(calls[1][2].query.page,2);
});
test('email mode serializes only recipient-bound grant inputs, never extra bearer token or URL fields',async()=>{
 const {api,calls}=fixture();await api.emailInvitations.create('org',{recipient_ref:'opaque-reference',role:'viewer',workspace_id:null,expires_in_hours:24,message:'Hello',token:'SECRET',acceptance_url:'https://evil.invalid'});
 assert.deepEqual(calls[0][2].body,{recipient_ref:'opaque-reference',role:'viewer',workspace_id:null,expires_in_hours:24,message:'Hello'});
});
test('email review accepts a UUID only and performs mutations once without retry',async()=>{
 const {api,calls}=fixture();assert.throws(()=>api.emailInvitations.review('legacy-bearer-secret'),/UUID/);
 await api.emailInvitations.accept(invitation);await api.emailInvitations.decline(invitation);assert.equal(calls.length,2);assert.equal(calls[0][0],'POST');assert.equal(calls[1][1],`/invitations/email/${invitation}/decline`);
});
test('monthly schedule preview is nonmutating and distinct from saving preferences',async()=>{
 const {api,calls}=fixture();const input={expected_revision:3,rules:[],digest:'monthly',schedule:{local_time:'09:30',weekday:0,day_of_month:31}};
 await api.notifications.previewPreferences(input);await api.notifications.updatePreferences(input);
 assert.equal(calls[0][0],'POST');assert.equal(calls[0][1],'/notifications/preferences/preview');assert.equal(calls[1][0],'PATCH');assert.deepEqual(calls[1][2].body,{...input,notification_locale:null,admin_summaries:null});
});
test('failed sends are surfaced without a client side retry',async()=>{
 let calls=0;const api=createCommunicationsApi({request:async()=>{calls++;throw new Error('failure');},stream:async function*(){}});
 await assert.rejects(api.emailInvitations.resend('org',invitation));assert.equal(calls,1);
});

test('actual email preview preserves past window and administrator opt-out but strips unknown payload fields',async()=>{const {api,calls}=fixture();await api.notifications.previewEmail({tenant_id:'org',preferences:{expected_revision:4,rules:[],digest:'weekly',admin_summaries:false,schedule:{local_time:'08:00',weekday:1,day_of_month:1},token:'SECRET'},window:{start_at:'2026-10-01T00:00:00Z',end_at:'2026-10-08T00:00:00Z',time_zone:'Europe/Madrid',subject:'OTHER'},send:true});assert.equal(calls[0][0],'POST');assert.equal(calls[0][1],'/notifications/preferences/email-preview');assert.deepEqual(calls[0][2].body,{tenant_id:'org',preferences:{expected_revision:4,notification_locale:null,admin_summaries:false,rules:[],digest:'weekly',schedule:{local_time:'08:00',weekday:1,day_of_month:1}},window:{start_at:'2026-10-01T00:00:00Z',end_at:'2026-10-08T00:00:00Z',time_zone:'Europe/Madrid'}});});
test('notification and delivery event filters use native kind query names and never leak arbitrary filter fields',async()=>{const {api,calls}=fixture();await api.notifications.list({event_kind:'security',read:'unread',tenant_id:'org',page:2,page_size:25,token:'SECRET'});await api.administration.deliveries('org',{event_kind:'digest',status:'queued',created_from:'2026-10-01T00:00:00Z',page:3,page_size:10,token:'SECRET'});assert.equal(calls[0][2].query.kind,'security');assert.equal(calls[1][2].query.kind,'digest');for(const call of calls){assert.equal('event_kind' in call[2].query,false);assert.equal('token' in call[2].query,false);}assert.equal(calls[0][2].query.read,'unread');assert.equal(calls[1][2].query.page,3);});
