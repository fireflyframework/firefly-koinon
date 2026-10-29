// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { expect, test } from '@playwright/test';
import { mockService } from './fixtures';
test('a separately installed Angular consumer renders the packed library and receives selection', async ({
  page,
}) => {
  await mockService(page);
  await page.goto('/consumer/');
  await expect(page.getByRole('heading', { name: 'External Angular consumer' })).toBeVisible();
  await page
    .getByRole('button', { name: /Reference library/ })
    .first()
    .click();
  await expect(page.locator('#host-selection')).toHaveText('Reference library');
  const color = await page
    .locator('ffk-workbench')
    .locator('button.primary')
    .first()
    .evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(color).toBe('rgb(255, 179, 74)');
  await expect(page.locator('header').first()).toHaveCSS('font-family', /Georgia/);
});
test('the custom element accepts a host client and emits typed selection without host CSS takeover', async ({
  page,
}) => {
  await mockService(page);
  await page.goto('/elements/');
  await page.waitForFunction(() => !!customElements.get('firefly-koinon'));
  await page.evaluate(async () => {
    const sdk = await import('/sdk/index.js');
    const element = document.querySelector('firefly-koinon') as HTMLElement & {
      client: unknown;
      tenantId: string;
      workspaceId: string;
      projectId: string;
      showNavigation: boolean;
    };
    element.tenantId = 'tenant-one';
    element.workspaceId = 'workspace-one';
    element.projectId = 'project-one';
    element.showNavigation = false;
    element.addEventListener('selectionChange', (event) => {
      const output = document.createElement('output');
      output.id = 'element-selection';
      output.textContent = (event as CustomEvent).detail.name;
      document.querySelector('header')!.append(output);
    });
    element.client = new sdk.KoinonClient({
      transport: new sdk.FetchTransport({ baseUrl: '/bff/api/v1', credentials: 'include' }),
    });
  });
  await page
    .getByRole('button', { name: /Reference library/ })
    .first()
    .click();
  await expect(page.locator('#element-selection')).toHaveText('Reference library');
  const styles = await page
    .locator('firefly-koinon')
    .locator('button.primary')
    .first()
    .evaluate((element) => ({
      color: getComputedStyle(element).backgroundColor,
      fontSize: getComputedStyle(element).fontSize,
    }));
  expect(styles.color).toBe('rgb(255, 179, 74)');
  expect(styles.fontSize).not.toBe('30px');
});
test('an embedded sign-in request is an event and does not navigate the host', async ({ page }) => {
  await mockService(page, { authenticated: false });
  await page.goto('/elements/');
  await page.waitForFunction(() => !!customElements.get('firefly-koinon'));
  await page.evaluate(async () => {
    const sdk = await import('/sdk/index.js');
    const element = document.querySelector('firefly-koinon') as HTMLElement & { client: unknown };
    element.addEventListener('authenticationRequired', () => {
      document.querySelector('header')!.setAttribute('data-auth-requested', 'true');
    });
    element.client = new sdk.KoinonClient({
      transport: new sdk.FetchTransport({ baseUrl: '/bff/api/v1', credentials: 'include' }),
    });
  });
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.locator('body > header')).toHaveAttribute('data-auth-requested', 'true');
  expect(page.url()).toContain('/elements/');
});

test('a host opens a focused chat and controls its sidebar without changing the host URL',async({page})=>{
  await mockService(page, { organizationAgent: 'reader' });
  await page.route('**/bff/api/v1/tenants/*/agents**',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({items:[{id:'reader',status:'ready',name:'koinon'}]})}));
  await page.goto('/elements/');
  await page.waitForFunction(()=>!!customElements.get('firefly-koinon'));
  await page.evaluate(async()=>{
    const sdk=await import('/sdk/index.js');
    const element=document.querySelector('firefly-koinon') as HTMLElement&{client:unknown;showNavigation:boolean;view:string;navigationCollapsed:boolean;tenantId:string};
    element.showNavigation=false;element.view='chat';element.navigationCollapsed=true;element.tenantId='tenant-one';
    element.addEventListener('navigationCollapsedChange',event=>element.setAttribute('data-collapsed',String((event as CustomEvent).detail)));
    element.client=new sdk.KoinonClient({transport:new sdk.FetchTransport({baseUrl:'/bff/api/v1',credentials:'include'})});
  });
  const host=page.locator('firefly-koinon');
  await expect(host.getByRole('textbox',{name:'Message koinon',exact:true})).toBeVisible();
  await expect(host.locator('ffk-conversation-sidebar')).not.toBeVisible();
  await expect(host.getByRole('navigation',{name:'Main navigation',exact:true})).toHaveCount(0);
  await expect(host.getByRole('searchbox',{name:'Search your knowledge',exact:true})).toHaveCount(0);
  await host.getByRole('button',{name:'Show conversations',exact:true}).click();
  await expect(host.locator('ffk-conversation-sidebar')).toBeVisible();
  await expect(host).toHaveAttribute('data-collapsed','false');
  expect(new URL(page.url()).pathname).toBe('/elements/');
});
