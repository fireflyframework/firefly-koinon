// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { context, mockService } from './fixtures';

const organization = (page: Page) =>
  page.getByRole('combobox', { name: 'Organization', exact: true });
async function setup(page: Page) {
  await mockService(page, { organizationAgent: 'reader' });
  const current = structuredClone(context);
  current.tenants[1].permissions.push('chat:use');
  const catalogs: string[] = [];
  const chatReads: string[] = [];
  await page.route('**/bff/api/v1/context', (route) => route.fulfill({ json: current }));
  await page.route('**/bff/api/v1/tenants/*/agents**', (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: 'reader',
            name: 'Knowledge reader',
            description: 'Controlled navigation fixture',
            provider_id: 'fixture-provider',
            model_id: 'fixture-model',
            tools: [],
            scope: {},
            instructions: '',
            enabled: true,
            revision: 1,
            status: 'ready',
            checks: [],
          },
        ],
      },
    }),
  );
  await page.route('**/bff/api/v1/tenants/*/chat/threads**', (route) =>
    route.fulfill({
      json: {
        items: [],
        total: 0,
        page: 1,
        page_size: 25,
        pages: 0,
      },
    }),
  );
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (/\/tenants\/[^/]+\/catalog$/.test(path)) catalogs.push(path);
    if (/\/tenants\/[^/]+\/(agents|chat\/threads)$/.test(path)) chatReads.push(path);
  });
  return { current, catalogs, chatReads };
}

test('management restores the chosen organization before catalog reads across reload and direct account/chat links', async ({
  page,
}) => {
  const state = await setup(page);
  await page.goto('/library');
  await organization(page).selectOption('tenant-two');
  await expect(organization(page)).toHaveValue('tenant-two');
  await expect(page.getByRole('status', { name: 'Working', exact: true })).toHaveCount(0);
  expect(state.catalogs).toEqual([
    '/bff/api/v1/tenants/tenant-one/catalog',
    '/bff/api/v1/tenants/tenant-two/catalog',
  ]);
  for (const path of ['/account/profile?retained=one#panel=two', '/chat', '/']) {
    state.catalogs.length = 0;
    await page.goto(path);
    await expect(organization(page)).toHaveValue('tenant-two');
    expect(state.catalogs.length).toBeGreaterThan(0);
    expect(state.catalogs.every((path) => path === '/bff/api/v1/tenants/tenant-two/catalog')).toBe(
      true,
    );
  }
  state.catalogs.length = 0;
  await page.reload();
  await expect(organization(page)).toHaveValue('tenant-two');
  expect(state.catalogs[0]).toBe('/bff/api/v1/tenants/tenant-two/catalog');
});

for (const screen of ['/chat', '/account/profile'])
  test(`changing organization from ${screen} keeps the host route and Library screen coherent`, async ({
    page,
  }) => {
    await setup(page);
    await page.goto(screen + '?retained=one#panel=two');
    await organization(page).selectOption('tenant-two');
    await expect(page).toHaveURL('/library?retained=one#panel=two');
    await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Profile & preferences', exact: true }),
    ).toHaveCount(0);
  });

test('a deferred organization catalog response cannot clobber a later Chat navigation', async ({
  page,
}) => {
  const state = await setup(page);
  let release!: () => void, requested!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const pending = new Promise<void>((resolve) => {
    requested = resolve;
  });
  await page.route('**/bff/api/v1/tenants/tenant-two/catalog**', async (route) => {
    requested();
    await gate;
    await route.fallback();
  });
  await page.goto('/chat');
  await organization(page).selectOption('tenant-two');
  await pending;
  await page.getByRole('button', { name: 'Chat', exact: true }).first().click();
  await expect(page).toHaveURL('/');
  release();
  await expect(page.getByRole('status', { name: 'Working', exact: true })).toHaveCount(0);
  await expect(page).toHaveURL('/');
  await expect(page.locator('ffk-chat-page')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Library', exact: true })).toHaveCount(0);
  await expect
    .poll(() => state.chatReads)
    .toEqual(
      expect.arrayContaining([
        '/bff/api/v1/tenants/tenant-two/agents',
        '/bff/api/v1/tenants/tenant-two/chat/threads',
      ]),
    );
});

test('fresh context validates a saved organization across reorder, identity change and revocation', async ({
  page,
}) => {
  const state = await setup(page);
  await page.goto('/library');
  await organization(page).selectOption('tenant-two');
  await expect(page.getByRole('status', { name: 'Working', exact: true })).toHaveCount(0);
  state.current.tenants.reverse();
  await page.reload();
  await expect(organization(page)).toHaveValue('tenant-two');
  state.current.tenants.reverse();
  state.current.subject = 'another-reader';
  state.catalogs.length = 0;
  await page.reload();
  await expect(organization(page)).toHaveValue('tenant-one');
  expect(state.catalogs).toEqual(['/bff/api/v1/tenants/tenant-one/catalog']);
  state.current.subject = context.subject;
  await page.reload();
  await expect(organization(page)).toHaveValue('tenant-two');
  state.current.tenants = [state.current.tenants[0]];
  state.catalogs.length = 0;
  await page.reload();
  await expect(organization(page)).toHaveValue('tenant-one');
  expect(state.catalogs).toEqual(['/bff/api/v1/tenants/tenant-one/catalog']);
  state.current.tenants = [];
  state.catalogs.length = 0;
  await page.reload();
  await expect(page.locator('ffk-shell')).toBeVisible();
  expect(state.catalogs).toEqual([]);
});

test('malformed tab state falls back before catalog reads', async ({ page }) => {
  const state = await setup(page);
  await page.addInitScript(() => {
    sessionStorage.setItem(
      'koinon.organization:/:synthetic.reviewer',
      '{"tenantId":"tenant-two","token":"private"}',
    );
  });
  await page.goto('/chat');
  await expect(organization(page)).toHaveValue('tenant-one');
  expect(state.catalogs).toEqual(['/bff/api/v1/tenants/tenant-one/catalog']);
  expect(
    await page.evaluate(() => sessionStorage.getItem('koinon.organization:/:synthetic.reviewer')),
  ).toBeNull();
});

test('denied tab storage preserves usable selection without affecting the management page', async ({
  page,
}) => {
  await setup(page);
  await page.addInitScript(() => {
    Object.defineProperty(window, 'sessionStorage', {
      get() {
        throw new DOMException('Denied', 'SecurityError');
      },
    });
  });
  await page.goto('/library');
  await organization(page).selectOption('tenant-two');
  await expect(organization(page)).toHaveValue('tenant-two');
  await page.getByRole('button', { name: 'Chat', exact: true }).first().click();
  await expect(page).toHaveURL('/');
  await page.reload();
  await expect(organization(page)).toHaveValue('tenant-one');
});

test('an explicit valid share organization wins over the saved organization before catalog reads', async ({
  page,
}) => {
  const state = await setup(page);
  await page.goto('/library');
  await organization(page).selectOption('tenant-two');
  await expect(page.getByRole('status', { name: 'Working', exact: true })).toHaveCount(0);
  state.catalogs.length = 0;
  await page.goto('about:blank');
  await page.goto('/#share=reviewed-answer&tenant=tenant-one');
  await expect(organization(page)).toHaveValue('tenant-one');
  expect(state.catalogs).toEqual(['/bff/api/v1/tenants/tenant-one/catalog']);
  expect(page.url()).not.toContain('reviewed-answer');
  const preferences = await page.evaluate(() =>
    Object.entries(sessionStorage).filter(([key]) => key.startsWith('koinon.organization:')),
  );
  expect(preferences.every(([, value]) => ['"tenant-one"', '"tenant-two"'].includes(value))).toBe(
    true,
  );
});

test('an accepted invitation selects its organization instead of a retained preference', async ({
  page,
}) => {
  const state = await setup(page);
  await page.goto('/library');
  await organization(page).selectOption('tenant-two');
  await expect(page.getByRole('status', { name: 'Working', exact: true })).toHaveCount(0);
  const token = 'controlled_invitation'.padEnd(43, 'a');
  await page.route('**/bff/api/v1/invitations/inspect', (route) =>
    route.fulfill({
      json: {
        id: 'invitation',
        tenant_id: 'tenant-one',
        tenant_name: 'Knowledge operations',
        workspace_id: null,
        workspace_name: null,
        role: 'viewer',
        expires_at: '2099-01-01T00:00:00Z',
      },
    }),
  );
  await page.route('**/bff/api/v1/invitations/redeem', (route) =>
    route.fulfill({
      json: {
        id: 'membership',
        tenant_id: 'tenant-one',
        subject: context.subject,
        workspace_id: null,
        role: 'viewer',
        active: true,
      },
    }),
  );
  await page.goto('about:blank');
  await page.goto('/#invite=' + token);
  await page.getByRole('button', { name: 'Accept invitation', exact: true }).click();
  await expect(organization(page)).toHaveValue('tenant-one');
  expect(state.catalogs.at(-1)).toBe('/bff/api/v1/tenants/tenant-one/catalog');
  await page.reload();
  await expect(organization(page)).toHaveValue('tenant-one');
});

test('retry restores the chosen authorized organization after a failed fresh-context request', async ({
  page,
}) => {
  const state = await setup(page);
  await page.goto('/library');
  await organization(page).selectOption('tenant-two');
  await expect(page.getByRole('status', { name: 'Working', exact: true })).toHaveCount(0);
  let failed = false;
  await page.route('**/bff/api/v1/context', async (route) => {
    if (!failed) {
      failed = true;
      return route.fulfill({ status: 503, json: { detail: 'Controlled context unavailable' } });
    }
    return route.fallback();
  });
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('Controlled context unavailable');
  state.catalogs.length = 0;
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(organization(page)).toHaveValue('tenant-two');
  expect(state.catalogs).toEqual(['/bff/api/v1/tenants/tenant-two/catalog']);
});

test('embedded organization selection emits context without reading or writing host URL or storage', async ({
  page,
}) => {
  await setup(page);
  await page.goto('/elements/?host=retained#panel');
  await page.waitForFunction(() => !!customElements.get('firefly-koinon'));
  await page.evaluate(async () => {
    const sdk = await import('/sdk/index.js');
    const element = document.querySelector('firefly-koinon') as HTMLElement & {
      client: unknown;
      tenantId: string;
    };
    const denied = {
      getItem() {
        throw new Error('Host storage read');
      },
      setItem() {
        throw new Error('Host storage write');
      },
      removeItem() {
        throw new Error('Host storage removal');
      },
    };
    Object.defineProperty(window, 'sessionStorage', { value: denied });
    Object.defineProperty(window, 'localStorage', { value: denied });
    element.tenantId = 'tenant-two';
    element.addEventListener('contextChange', (event) =>
      element.setAttribute('data-tenant', (event as CustomEvent).detail.tenantId),
    );
    element.client = new sdk.KoinonClient({
      transport: new sdk.FetchTransport({ baseUrl: '/bff/api/v1', credentials: 'include' }),
    });
  });
  await expect(organization(page)).toHaveValue('tenant-two');
  await organization(page).selectOption('tenant-one');
  await expect(page.locator('firefly-koinon')).toHaveAttribute('data-tenant', 'tenant-one');
  await expect(page).toHaveURL('/elements/?host=retained#panel');
});

for (const width of [1440, 390])
  test(`retained organization stays visible in account and Chat at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setup(page);
    await page.goto('/library');
    if (width < 1100)
      await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
    await organization(page).selectOption('tenant-two');
    if (width < 1100)
      await page
        .getByRole('dialog', { name: 'Navigation', exact: true })
        .getByRole('button', { name: 'Close navigation', exact: true })
        .click();
    await expect(page.getByRole('status', { name: 'Working', exact: true })).toHaveCount(0);
    const directory = resolve('.qualification-v22/captures');
    await mkdir(directory, { recursive: true });
    for (const path of ['/account/profile', '/chat']) {
      await page.goto(path);
      if (width < 1100)
        await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
      await expect(organization(page)).toHaveValue('tenant-two');
      if (width < 1100) {
        await page.screenshot({
          path: resolve(
            directory,
            `organization-${path.includes('account') ? 'account' : 'chat'}-${width}.png`,
          ),
          animations: 'disabled',
          fullPage: true,
        });
        await page
          .getByRole('dialog', { name: 'Navigation', exact: true })
          .getByRole('button', { name: 'Close navigation', exact: true })
          .click();
      }
      await expect(page.locator('ffk-shell')).toBeVisible();
      if (path === '/chat') {
        await expect(
          page.getByRole('textbox', { name: 'Message koinon', exact: true }),
        ).toBeVisible();
        await expect(page.getByRole('alert')).toHaveCount(0);
      }
      await page.screenshot({
        path: resolve(directory, `${path.includes('account') ? 'account' : 'chat'}-${width}.png`),
        animations: 'disabled',
        fullPage: true,
      });
    }
  });
