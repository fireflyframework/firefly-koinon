// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { expect, test } from '@playwright/test';
import { fixtures, mockService,mockReaderAccounts,chooseReaderMode } from './fixtures';

for (const width of [320, 390, 1440]) for (const theme of ['light', 'dark']) {
  test(`reader Library continues an empty page and clears old results at ${width}px ${theme}`, async ({page}, info) => {
    const spanish=theme==='dark';
    await page.setViewportSize({width,height:900});
    await mockService(page);
    await page.route('**/bff/api/v1/profile',route=>route.fulfill({json:{subject:'synthetic.reviewer',display_name:'Alex',locale:spanish?'es-ES':'en-US',time_zone:'UTC',response_language:spanish?'es':'en',avatar_url:null,avatar_version:null}}));
    await page.addInitScript(value=>localStorage.setItem('koinon-theme',value),theme);
    await page.route('**/bff/api/v1/tenants/*/content-sources/**',route=>{
      const path=new URL(route.request().url()).pathname;
      if(path.endsWith('/reader-selection'))return route.fulfill({json:{revision:1,connections:[]}});
      if(path.endsWith('/capabilities'))return route.fulfill({json:{accounts_available:true,synchronization_available:true,inbound_only:true,providers:[],modes:[],formats:[],schedule:{}}});
      return route.fulfill({json:{items:[],next_cursor:null}});
    });
    const requests:Record<string,unknown>[]=[];
    await page.route('**/bff/api/v1/tenants/*/catalog/browse',route=>{
      const body=route.request().postDataJSON();requests.push(body);
      const local=Array.isArray(body.reader_source_connections)&&body.reader_source_connections.length===0;
      return route.fulfill({json:{items:local?[{...fixtures[0],name:'Local workspace'}]:body.cursor?[{...fixtures[0],name:'Earlier workspace'}]:[],actors:{},next_cursor:!local&&!body.cursor?'opaque-reader-page':null,total:null,total_is_exact:false}});
    });
    const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
    await page.goto('/library');
    const more=page.getByRole('button',{name:spanish?'Seguir explorando':'Continue browsing',exact:true});
    await expect(more).toBeVisible();
    await more.focus();await page.keyboard.press('Enter');
    await expect(page.getByRole('button',{name:'Earlier workspace',exact:true})).toBeVisible();
    expect(requests.at(-1)).toMatchObject({cursor:'opaque-reader-page',reader_source_connections:null});
    expect(requests.at(-1)).not.toHaveProperty('page');
    const sourceTrigger=page.getByRole('button',{name:spanish?/^Fuentes para la biblioteca/:/^Sources for Library/});
    await sourceTrigger.click();
    await page.getByRole('radio',{name:spanish?'Usar solo conocimiento local':'Use local knowledge only',exact:true}).check();
    await page.getByRole('button',{name:spanish?'Aplicar':'Apply',exact:true}).click();
    await expect(page.getByRole('button',{name:'Local workspace',exact:true})).toBeVisible();
    await expect(sourceTrigger).toBeFocused();
    await expect(page.getByRole('radio')).toHaveCount(0);
    await expect(sourceTrigger).toContainText(spanish?'Solo conocimiento local':'Local knowledge only');
    await expect(page.getByText('Earlier workspace',{exact:true})).toHaveCount(0);
    expect(requests.at(-1)).toMatchObject({reader_source_connections:[]});
    expect(requests.at(-1)?.['cursor']).toBeUndefined();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    if(width<700){
      const sort=await page.locator('.mobile-sort').boundingBox(),count=await page.locator('.library-toolbar .item-count').boundingBox();
      expect(sort&&count&&(sort.x+sort.width<=count.x||count.x+count.width<=sort.x||sort.y+sort.height<=count.y||count.y+count.height<=sort.y)).toBe(true);
    }
    if(width===1440){
      await page.evaluate(()=>document.documentElement.style.zoom='2');
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      await expect(sourceTrigger).toBeVisible();
      await page.screenshot({path:info.outputPath(`reader-library-200percent-${theme}.png`),fullPage:true});
      await page.evaluate(()=>document.documentElement.style.zoom='');
    }
    expect(errors).toEqual([]);
    await page.screenshot({path:info.outputPath(`reader-library-${width}-${theme}.png`),fullPage:true});
  });
}

test('archived Library continues an empty page without broadening local-only intent',async({page})=>{
  await mockService(page);await mockReaderAccounts(page);
  const archiveBodies:Record<string,unknown>[]=[];
  await page.route('**/bff/api/v1/tenants/*/catalog/browse',route=>{
    const body=route.request().postDataJSON();
    if(body.status!=='archived')return route.fallback();
    archiveBodies.push(body);
    expect(body.reader_source_connections).toEqual([]);
    return route.fulfill({json:{items:body.cursor?[{...fixtures[0],name:'Local archived workspace',status:'archived'}]:[],actors:{},next_cursor:body.cursor?null:'archive-continuation',total:null,total_is_exact:false}});
  });
  await page.goto('/library');await chooseReaderMode(page,'local');
  await page.getByRole('button',{name:'Archived',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Archived items'});
  await dialog.getByRole('button',{name:'Continue browsing',exact:true}).click();
  await expect(dialog.getByText('Local archived workspace',{exact:true})).toBeVisible();
  expect(archiveBodies.at(-1)).toMatchObject({cursor:'archive-continuation',reader_source_connections:[]});
  expect(archiveBodies.at(-1)).not.toHaveProperty('page');
});

test('refresh preserves an authorized selection and announces removal with list focus',async({page})=>{
  await mockService(page);
  await page.route('**/bff/api/v1/tenants/*/catalog/browse',route=>{
    const body=route.request().postDataJSON();
    return route.fulfill({json:{items:body.q==='removed'?[]:[{...fixtures[0],name:body.q==='updated'?'Updated authorized workspace':'Earlier workspace'}],actors:{},next_cursor:null,total:null,total_is_exact:false}});
  });
  await page.goto('/library');
  await page.getByRole('button',{name:'Details for Earlier workspace',exact:true}).click();
  const filter=page.getByRole('searchbox',{name:'Filter this folder by name',exact:true});
  await filter.fill('updated');await page.getByRole('button',{name:'Apply folder filter',exact:true}).click();
  await expect(page.getByRole('complementary',{name:'Resource details'})).toContainText('Updated authorized workspace');
  await filter.fill('removed');await page.getByRole('button',{name:'Apply folder filter',exact:true}).click();
  await expect(page.getByRole('complementary',{name:'Resource details'})).toHaveCount(0);
  await expect(page.getByText('The available items changed.',{exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Library',exact:true})).toBeFocused();
});
