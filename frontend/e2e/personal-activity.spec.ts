// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {test,expect} from '@playwright/test';
import {mockService,context,openAdministration} from './fixtures';
import {mkdir} from 'node:fs/promises';
function summary(tenant:string,audience='personal'){
 const observed={value:3,status:'observed'};
 return {tenant_id:tenant,audience,window:{start_at:'2026-10-01T00:00:00Z',end_at:'2026-10-02T00:00:00Z',time_zone:'UTC'},coverage:{observed_since:null,complete_window:true},knowledge:{created:observed,updated:observed,consulted:observed},top_projects:[{project_id:'project-'+tenant,name:tenant==='tenant-one'?'First organization project':'Second organization project',knowledge:{created:observed,updated:observed,consulted:observed}}],mcp:{requests:observed,tool_calls:observed,succeeded:observed,failed:observed,rejected:observed,average_duration_ms:observed,p95_duration_ms:observed},models:{input_tokens:observed,output_tokens:observed,embedding_tokens:observed,cost:{amount:null,status:'unavailable'}}};
}
for(const administrator of [false,true])for(const width of [1440,390])test(`${administrator?'administrator':'reader'} uses a personal-only activity view at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:960});await mockService(page);
 const owner=structuredClone(context);if(!administrator){owner.tenants[0].roles=['viewer'];owner.tenants[0].permissions=['catalog:read','knowledge:search'];}
 else {owner.tenants[0].permissions.push('activity:read');owner.memberships=[{id:'admin',tenant_id:'tenant-one',subject:owner.subject,role:'admin',active:true,workspace_id:null}];}
 await page.route('**/bff/api/v1/context',route=>route.fulfill({json:owner}));
 const privileged:string[]=[],personal:string[]=[];
 page.on('request',request=>{const path=new URL(request.url()).pathname;if(path.includes('/jobs')||path.endsWith('/activity/administration'))privileged.push(path);if(path.endsWith('/activity/personal'))personal.push(path);});
 await page.route('**/activity/{personal,administration}',route=>{const path=new URL(route.request().url()).pathname;return route.fulfill({json:{...summary(path.split('/')[5],path.endsWith('/personal')?'personal':'organization_administrators'),window:route.request().postDataJSON()}});});
 await page.goto('/my-activity');await expect(page.getByRole('heading',{name:'My activity',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'Your knowledge activity',exact:true})).toBeVisible();
 await expect(page.getByRole('combobox',{name:'Summary audience',exact:true})).toHaveCount(0);await expect(page.getByRole('heading',{name:'Processing jobs',exact:true})).toHaveCount(0);await expect(page.locator('ffk-processing-history')).toHaveCount(0);expect(privileged).toEqual([]);expect(personal.length).toBeGreaterThan(0);
 await expect(page.getByText('First organization project',{exact:true})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 const start=(await page.getByLabel('From date (UTC)',{exact:true}).boundingBox())!,end=(await page.getByLabel('Until date, excluded (UTC)',{exact:true}).boundingBox())!;expect(Math.abs(start.y-end.y)).toBeLessThanOrEqual(1);
 const output=process.env['KOINON_BRAND_SCREENSHOTS'];if(output){await mkdir(output,{recursive:true});await page.screenshot({path:`${output}/${administrator?'admin':'reader'}-my-activity-${width}.png`});}
 if(width===1440){
  await page.getByRole('combobox',{name:'Organization',exact:true}).selectOption('tenant-two');
  await expect(page.getByText('First organization project',{exact:true})).toHaveCount(0);
  await page.locator('ffk-shell .topbar').getByRole('button',{name:'My activity',exact:true}).click();await expect(page.getByText('Second organization project',{exact:true})).toBeVisible();expect(privileged).toEqual([]);
 }
 if(administrator && width===390){await openAdministration(page,'Activity');await expect(page.getByRole('heading',{name:'Activity',exact:true})).toBeVisible();expect(privileged.some(path=>path.includes('/jobs'))).toBe(true);}
 if(!administrator){await page.goto('/activity');await expect(page.getByRole('heading',{name:'Activity',exact:true})).toHaveCount(0);expect(privileged).toEqual([]);}
});
