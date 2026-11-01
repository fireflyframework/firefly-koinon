// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {test,expect} from '@playwright/test';
import {mockService,openAdministration} from './fixtures';
import {mkdir} from 'node:fs/promises';
for(const width of [1440,1200])test(`workspace rails share geometry and preserve collapse at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:960});await mockService(page);await page.goto('/chat');
 const chatRail=(await page.locator('ffk-conversation-sidebar').boundingBox())!;
 const nav=page.locator('ffk-shell .topbar').getByRole('navigation',{name:'Main navigation',exact:true});
 await openAdministration(page,'Settings');
 const rail=page.getByRole('navigation',{name:'Settings sections',exact:true}),title=page.getByRole('heading',{name:'Providers',exact:true});
 await expect(rail).toBeVisible();const r=(await rail.boundingBox())!,heading=(await title.boundingBox())!,primary=(await nav.boundingBox())!;
 expect(Math.abs(r.width-chatRail.width)).toBeLessThanOrEqual(1);expect(Math.abs(primary.x-heading.x)).toBeLessThanOrEqual(1);
 const toggle=page.getByRole('button',{name:'Hide settings navigation',exact:true});
 await toggle.click();await expect(rail).toBeHidden();await expect(page.getByRole('button',{name:'Show settings navigation',exact:true})).toBeFocused();
 await page.reload();await expect(page.getByRole('button',{name:'Show settings navigation',exact:true})).toHaveAttribute('aria-expanded','false');await expect(rail).toBeHidden();
 if(process.env['KOINON_BRAND_SCREENSHOTS']){const output=process.env['KOINON_BRAND_SCREENSHOTS'];await mkdir(output!,{recursive:true});await page.screenshot({path:`${output}/settings-shared-rail-collapsed-${width}.png`});}
 await page.getByRole('button',{name:'Show settings navigation',exact:true}).click();await expect(rail).toBeVisible();await expect(title).toBeVisible();
 const output=process.env['KOINON_BRAND_SCREENSHOTS'];if(output){await mkdir(output,{recursive:true});await page.screenshot({path:`${output}/settings-shared-rail-${width}.png`});}
 await nav.getByRole('button',{name:'Chat',exact:true}).click();await page.getByRole('button',{name:'Hide conversations',exact:true}).click();await expect(page.locator('ffk-conversation-sidebar')).toBeHidden();
 await openAdministration(page,'Settings');await expect(rail).toBeHidden();await page.getByRole('button',{name:'Show settings navigation',exact:true}).click();await expect(rail).toBeVisible();
});
