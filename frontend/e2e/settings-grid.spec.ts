// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { openAdministration, mockService } from './fixtures';
import { mkdir } from 'node:fs/promises';
for (const width of [3840,1440,1200,390]) test(`Settings preserves a bounded navigation column at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:960});await mockService(page);await page.goto('/library');await openAdministration(page,'Settings');
 const nav=page.getByRole('navigation',{name:'Settings sections',exact:true}), content=page.getByRole('region',{name:'Settings content',exact:true});
 if(width>760){
  await nav.getByRole('button',{name:'Providers',exact:true}).click();
  await expect(nav).toBeVisible();const n=(await nav.boundingBox())!,c=(await content.boundingBox())!;
  expect(n.width).toBeLessThanOrEqual(300);expect(c.width).toBeGreaterThan(width/2);expect(c.x).toBeGreaterThanOrEqual(n.x+n.width);
 }else{await page.getByRole('combobox',{name:'Settings section',exact:true}).selectOption('providers');await expect(nav).toBeHidden();await expect(content).toBeVisible();expect((await content.boundingBox())!.width).toBeGreaterThan(width-64);}
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 const output=process.env['KOINON_BRAND_SCREENSHOTS'];if(output){await mkdir(output,{recursive:true});await page.screenshot({path:`${output}/settings-providers-${width}.png`});}
});
