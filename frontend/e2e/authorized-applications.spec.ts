// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import type { AuthorizedApplication } from '@fireflyframework/koinon-sdk';
import { mockService, context as fixtureContext } from './fixtures';

const record = (
  id: string,
  name: string,
  status: AuthorizedApplication['status'] = 'active',
): AuthorizedApplication => ({
  id,
  client_id: 'client-' + id,
  name,
  resource: 'https://knowledge.example.test/mcp',
  tenant_id: 'tenant-one',
  tenant_name: 'Knowledge operations',
  workspace_id: 'workspace-one',
  workspace_name: 'Research operations',
  scopes: ['catalog:read', 'knowledge:search', 'query:execute'],
  status,
  connected_at:
    status === 'active'
      ? id === 'research'
        ? '2026-10-28T09:45:00Z'
        : '2026-10-28T09:40:00Z'
      : '2026-10-27T09:45:00Z',
  expires_at:
    status === 'active'
      ? id === 'research'
        ? '2026-10-28T10:45:00Z'
        : '2026-10-28T10:40:00Z'
      : '2026-10-27T10:45:00Z',
  last_used_at: status === 'active' ? '2026-10-28T10:23:49Z' : null,
  revoked_at: status === 'revoked' ? '2026-10-27T10:25:00Z' : null,
});
async function setup(page: Page, count = 4) {
  await page.clock.setFixedTime(new Date('2026-10-28T10:30:00Z'));
  await mockService(page);
  const rows = [
    record('research', 'Research desktop'),
    record('notebook', 'Analytics notebook'),
    record('expired', 'Review companion', 'expired'),
    record('revoked', 'Previous connection', 'revoked'),
  ];
  for (let index = 4; index < count; index++)
    rows.push(record('app-' + index, 'Research connector ' + index));
  const requests: { method: string; path: string; query: string }[] = [];
  let fail = false;
  await page.route('**/bff/api/v1/authorized-applications**', async (route) => {
    const request = route.request(),
      url = new URL(request.url());
    requests.push({ method: request.method(), path: url.pathname, query: url.search });
    if (fail)
      return route.fulfill({
        status: 503,
        contentType: 'application/problem+json',
        body: JSON.stringify({ detail: 'Temporary failure' }),
      });
    const id = url.pathname.split('/')[5],
      row = rows.find((value) => value.id === id);
    if (request.method() === 'DELETE') {
      expect(request.headers()['x-xsrf-token']).toBe('synthetic-csrf+token');
      expect(row).toBeTruthy();
      row!.status = 'revoked';
      row!.revoked_at = '2026-10-28T10:30:00Z';
      return route.fulfill({ status: 204 });
    }
    if (id) return route.fulfill({ contentType: 'application/json', body: JSON.stringify(row) });
    const query = url.searchParams,
      q = (query.get('q') || '').toLowerCase(),
      status = query.get('status') || 'all';
    const filtered = rows.filter(
      (value) =>
        value.name.toLowerCase().includes(q) && (status === 'all' || value.status === status),
    );
    const sort = query.get('sort') || 'connected_at',
      direction = query.get('order') === 'asc' ? 1 : -1;
    filtered.sort(
      (a, b) =>
        String(a[sort as keyof AuthorizedApplication] || '').localeCompare(
          String(b[sort as keyof AuthorizedApplication] || ''),
        ) * direction || a.id.localeCompare(b.id),
    );
    const pageNumber = Number(query.get('page') || 1),
      pageSize = Number(query.get('page_size') || 25);
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: filtered.slice((pageNumber - 1) * pageSize, pageNumber * pageSize),
        total: filtered.length,
        page: pageNumber,
        page_size: pageSize,
        pages: Math.ceil(filtered.length / pageSize),
      }),
    });
  });
  return {
    rows,
    requests,
    fail: (value: boolean) => {
      fail = value;
    },
  };
}
async function open(page: Page, originWidth?: number) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  if (originWidth) await capture(page, `account-menu-${originWidth}`);
  await page.getByRole('menuitem', { name: 'Authorized applications', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Authorized applications', exact: true }),
  ).toBeVisible();
}
async function capture(page: Page, name: string) {
  const directory = resolve('../../control/frontend-captures/account-pages-v21');
  await mkdir(directory, { recursive: true });
  await page.evaluate(() => {
    if (document.getElementById('applications-fixture-caption')) return;
    const mark = document.createElement('div');
    mark.id = 'applications-fixture-caption';
    mark.textContent = 'Controlled application API fixtures · UI review only';
    mark.style.cssText =
      'position:fixed;bottom:0;left:0;right:0;z-index:9999;padding:5px 12px;background:#855414;color:white;font:10px system-ui;text-align:center;pointer-events:none';
    document.body.append(mark);
  });
  await page.screenshot({
    path: resolve(directory, name + '.png'),
    fullPage: true,
    animations: 'disabled',
  });
}
async function fullyVisible(page: Page, label: string, role: 'button' | 'heading' = 'button') {
  const locator =
    label === 'Revoke access'
      ? page
          .getByRole('region', { name: 'Revoke application confirmation', exact: true })
          .getByRole(role, { name: label, exact: true })
      : page.getByRole(role, { name: label, exact: true });
  await expect(locator).toBeVisible();
  expect(
    await locator.evaluate((element) => {
      const bounds = element.getBoundingClientRect(),
        tolerance = 1;
      if (
        bounds.top < -tolerance ||
        bounds.left < -tolerance ||
        bounds.bottom > innerHeight + tolerance ||
        bounds.right > innerWidth + tolerance
      )
        return false;
      let parent: Element | null = element.parentElement;
      while (parent) {
        const style = getComputedStyle(parent),
          clip = parent.getBoundingClientRect();
        if (
          /auto|scroll|hidden|clip/.test(style.overflowY) &&
          (bounds.top < clip.top + parent.clientTop - tolerance ||
            bounds.bottom > clip.top + parent.clientTop + parent.clientHeight + tolerance)
        )
          return false;
        if (
          /auto|scroll|hidden|clip/.test(style.overflowX) &&
          (bounds.left < clip.left + parent.clientLeft - tolerance ||
            bounds.right > clip.left + parent.clientLeft + parent.clientWidth + tolerance)
        )
          return false;
        parent =
          parent.parentElement ||
          (parent.getRootNode() instanceof ShadowRoot
            ? (parent.getRootNode() as ShadowRoot).host
            : null);
      }
      return true;
    }),
    label + ' must be fully visible through every clipping ancestor',
  ).toBe(true);
}
test('applications use separate list/detail/revoke HTTP and never show token controls', async ({
  page,
}) => {
  const fixture = await setup(page);
  await open(page);
  const row = page.locator('.application-row').filter({ hasText: 'Research desktop' });
  await row.getByRole('button', { name: 'Review permissions', exact: true }).click();
  await expect(
    page.getByRole('region', { name: 'Application permissions', exact: true }),
  ).toContainText('Browse knowledge');
  await expect(
    page.getByRole('region', { name: 'Application permissions', exact: true }),
  ).toContainText('Query datasets');
  await expect(
    page.getByText('Activity times are approximate and update at most every five minutes.', {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create a token', exact: true })).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: /Copy token|Add application|Refresh connection/ }),
  ).toHaveCount(0);
  await row.getByRole('button', { name: 'Revoke access', exact: true }).click();
  expect(fixture.requests.filter((value) => value.method === 'DELETE')).toHaveLength(0);
  await page.getByRole('button', { name: 'Keep access', exact: true }).click();
  await expect(row.getByRole('button', { name: 'Revoke access', exact: true })).toBeFocused();
  await row.getByRole('button', { name: 'Revoke access', exact: true }).click();
  await page
    .getByRole('region', { name: 'Revoke application confirmation' })
    .getByRole('button', { name: 'Revoke access', exact: true })
    .click();
  await expect(page.getByText('Application access revoked.', { exact: true })).toBeVisible();
  await expect(
    row.locator('.connection-status').getByText('Revoked', { exact: true }),
  ).toBeVisible();
  expect(fixture.requests.filter((value) => value.method === 'DELETE')).toHaveLength(1);
});
test('search status sort and pagination are sent to the server', async ({ page }) => {
  const fixture = await setup(page, 31);
  await open(page);
  await page
    .getByRole('button', { name: 'Next authorized applications page', exact: true })
    .click();
  await expect(
    page.getByRole('navigation', { name: 'Authorized applications pagination' }),
  ).toContainText('Page 2 of 2');
  await page.getByRole('searchbox', { name: 'Search applications', exact: true }).fill('Research');
  await page.getByRole('button', { name: 'Apply application filters', exact: true }).click();
  await page
    .getByRole('combobox', { name: 'Application status', exact: true })
    .selectOption('active');
  await page
    .getByRole('combobox', { name: 'Sort applications', exact: true })
    .selectOption('name:asc');
  await expect.poll(() => fixture.requests.at(-1)?.query).toContain('sort=name');
  const last = new URLSearchParams(fixture.requests.at(-1)!.query);
  expect(last.get('q')).toBe('Research');
  expect(last.get('status')).toBe('active');
  expect(last.get('page')).toBe('1');
  await page
    .getByRole('combobox', { name: 'Sort applications', exact: true })
    .selectOption('name:desc');
  await expect.poll(() => fixture.requests.at(-1)?.query).toContain('order=desc');
});
test('empty filtered state and load failure give honest recovery', async ({ page }) => {
  const fixture = await setup(page);
  await open(page);
  await page.getByRole('searchbox', { name: 'Search applications', exact: true }).fill('missing');
  await page.getByRole('button', { name: 'Apply application filters', exact: true }).click();
  await expect(
    page.getByText('No applications match these filters.', { exact: true }),
  ).toBeVisible();
  await capture(page, 'applications-empty-1440');
  fixture.fail(true);
  await page.getByRole('button', { name: 'Clear application filters', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText(
    'Authorized applications could not be loaded.',
  );
  await expect(page.getByText('No authorized applications yet.', { exact: true })).toHaveCount(0);
  await capture(page, 'applications-error-1440');
  fixture.fail(false);
  await page.getByRole('button', { name: 'Try loading applications again', exact: true }).click();
  await expect(
    page.locator('.application-row').filter({ hasText: 'Research desktop' }),
  ).toBeVisible();
});

for (const width of [1440, 390, 320])
  test(`authorized applications dark layout ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setup(page);
    await page.goto('/');
    await page.getByRole('button', { name: 'Account menu', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Use dark theme', exact: true }).click();
    await expect(page.locator('ffk-workbench')).toHaveClass(/koinon-dark/);
    await page.getByRole('menuitem', { name: 'Authorized applications', exact: true }).click();
    await expect(
      page.locator('.application-row').filter({ hasText: 'Research desktop' }),
    ).toBeVisible();
    expect(
      await page.locator('.account-page').evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    await capture(page, `applications-dark-${width}`);
  });

test('embedded identity change clears an in-flight permission view without showing a false empty account', async ({
  page,
}) => {
  await setup(page);
  let waiting = false,
    finish!: () => void;
  await page.route('**/bff/api/v1/authorized-applications/research', async (route) => {
    waiting = true;
    await new Promise<void>((resolve) => {
      finish = resolve;
    });
    await route
      .fulfill({
        contentType: 'application/json',
        body: JSON.stringify(record('research', 'Previous identity application')),
      })
      .catch(() => {});
  });
  await page.goto('/elements/');
  await page.waitForFunction(() => !!customElements.get('firefly-koinon'));
  const bind = async () =>
    page.evaluate(async () => {
      const sdk = await import('/sdk/index.js');
      const element = document.querySelector('firefly-koinon') as HTMLElement & {
        client: unknown;
        tenantId: string;
        showNavigation: boolean;
      };
      element.tenantId = 'tenant-one';
      element.showNavigation = true;
      element.client = new sdk.KoinonClient({
        transport: new sdk.FetchTransport({ baseUrl: '/bff/api/v1', credentials: 'include' }),
      });
    });
  await bind();
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Authorized applications', exact: true }).click();
  await page
    .locator('.application-row')
    .filter({ hasText: 'Research desktop' })
    .getByRole('button', { name: 'Review permissions', exact: true })
    .click();
  await expect.poll(() => waiting).toBe(true);
  await bind();
  finish();
  await expect(
    page.locator('.application-row').filter({ hasText: 'Research desktop' }),
  ).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'Application permissions', exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText('No authorized applications yet.', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Previous identity application', { exact: true })).toHaveCount(0);
});
for (const width of [1440, 390, 320])
  test(`connection review and revoke keyboard layout ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setup(page);
    await open(page);
    const directory = resolve('../../control/frontend-captures/account-pages-v21');
    await mkdir(directory, { recursive: true });
    await capture(page, `applications-list-${width}`);
    const row = page.locator('.application-row').filter({ hasText: 'Research desktop' });
    await row.getByRole('button', { name: 'Review permissions', exact: true }).click();
    await page.getByRole('region', { name: 'Application permissions', exact: true }).waitFor();
    expect(
      await page.locator('.account-page').evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    await page.screenshot({
      path: resolve(directory, `applications-light-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    await row.getByRole('button', { name: 'Revoke access', exact: true }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Revoke access?', exact: true })).toBeFocused();
    await fullyVisible(page, 'Keep access');
    await fullyVisible(page, 'Revoke access');
    await page.screenshot({
      path: resolve(directory, `applications-confirm-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', { name: 'Keep access', exact: true })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(row.getByRole('button', { name: 'Revoke access', exact: true })).toBeFocused();
    await page
      .getByRole('navigation', { name: 'Authorized applications pagination', exact: true })
      .scrollIntoViewIfNeeded();
    await fullyVisible(page, 'Next authorized applications page');
    await fullyVisible(page, 'Previous authorized applications page');
    await capture(page, `applications-pagination-${width}`);
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page
      .getByRole('navigation', { name: 'Breadcrumb', exact: true })
      .getByRole('button', { name: 'Library', exact: true })
      .click();
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  });

for (const width of [1440, 390, 320])
  test(`v21 account page prototype ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setup(page);
    await page.route('**/bff/api/v1/tokens**', async (route) => {
      const scopes = new URL(route.request().url()).pathname.endsWith('/scopes');
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(
          scopes
            ? {
                items: [{ id: 'catalog:read', name: 'Read library', dependencies: [] }],
                max_lifetime_days: 90,
                max_active_per_user: 10,
              }
            : { items: [], total: 0, page: 1, page_size: 25, pages: 0 },
        ),
      });
    });
    await open(page, width);
    await expect(page).toHaveURL(/\/account\/applications$/);
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(
      page.getByRole('heading', { name: 'Authorized applications', exact: true }),
    ).toBeFocused();
    await expect(
      page.getByRole('navigation', { name: 'Account sections', exact: true }),
    ).toBeVisible();
    await capture(page, `account-applications-${width}`);
    const row = page.locator('.application-row').filter({ hasText: 'Research desktop' });
    const review = row.getByRole('button', { name: 'Review permissions', exact: true });
    await expect(review).toHaveClass(/neutral/);
    if (width < 700) expect((await review.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await expect(review.locator('ffk-icon svg path')).toHaveAttribute('d', /M12 22/);
    await review.click();
    await expect(
      page.getByRole('region', { name: 'Application permissions', exact: true }),
    ).toBeVisible();
    await capture(page, `account-review-${width}`);
    await row.getByRole('button', { name: 'Revoke access', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Revoke access?', exact: true })).toBeFocused();
    await fullyVisible(page, 'Keep access');
    await fullyVisible(page, 'Revoke access');
    await capture(page, `account-revoke-${width}`);
    await page.getByRole('button', { name: 'Keep access', exact: true }).click();

    await page
      .getByRole('navigation', { name: 'Account sections', exact: true })
      .getByRole('button', { name: 'Profile & preferences', exact: true })
      .click();
    await expect(page).toHaveURL(/\/account\/profile$/);
    await expect(
      page.getByRole('heading', { name: 'Profile & preferences', exact: true }),
    ).toBeVisible();
    await capture(page, `account-profile-${width}`);
    await page
      .getByRole('navigation', { name: 'Account sections', exact: true })
      .getByRole('button', { name: 'API tokens', exact: true })
      .click();
    await expect(page).toHaveURL(/\/account\/tokens$/);
    await expect(page.getByRole('heading', { name: 'API tokens', exact: true })).toBeVisible();
    await capture(page, `account-tokens-${width}`);
  });

test('account URLs restore on back and forward without duplicate history or lost host parameters', async ({
  page,
}) => {
  await setup(page);
  await page.goto('/account/applications?retained=one#panel=two');
  await expect(
    page.getByRole('heading', { name: 'Authorized applications', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Chat', exact: true }).first().click();
  await expect(page).toHaveURL('/chat?retained=one#panel=two');
  await page.goBack();
  await expect(page).toHaveURL('/account/applications?retained=one#panel=two');
  await expect(
    page.getByRole('heading', { name: 'Authorized applications', exact: true }),
  ).toBeVisible();
  await page.goForward();
  await expect(page).toHaveURL('/chat?retained=one#panel=two');
  await expect(
    page.getByRole('heading', { name: 'Authorized applications', exact: true }),
  ).toHaveCount(0);
});

test('embedded account navigation emits host events without rewriting its URL', async ({
  page,
}) => {
  await setup(page);
  await page.goto('/elements/?host=retained#host-panel');
  await page.waitForFunction(() => !!customElements.get('firefly-koinon'));
  await page.evaluate(async () => {
    const sdk = await import('/sdk/index.js');
    const element = document.querySelector('firefly-koinon') as HTMLElement & {
      client: unknown;
      tenantId: string;
      showNavigation: boolean;
      accountSection: string | null;
    };
    element.tenantId = 'tenant-one';
    element.showNavigation = true;
    element.client = new sdk.KoinonClient({
      transport: new sdk.FetchTransport({ baseUrl: '/bff/api/v1', credentials: 'include' }),
    });
    element.addEventListener('accountSectionChange', (event) =>
      element.setAttribute('data-account-section', String((event as CustomEvent).detail)),
    );
  });
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Authorized applications', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Authorized applications', exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL('/elements/?host=retained#host-panel');
  await expect(page.locator('firefly-koinon')).toHaveAttribute(
    'data-account-section',
    'applications',
  );
  await page.evaluate(() => {
    (
      document.querySelector('firefly-koinon') as HTMLElement & { accountSection: string | null }
    ).accountSection = 'profile';
  });
  await expect(
    page.getByRole('heading', { name: 'Profile & preferences', exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL('/elements/?host=retained#host-panel');
  await capture(page, 'account-embedded-uri');
});

test('changing embedded client identity clears an ephemeral personal token secret', async ({
  page,
}) => {
  await setup(page);
  await page.route('**/bff/api/v1/tokens**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith('/scopes')
      ? {
          items: [{ id: 'catalog:read', name: 'Read library', dependencies: [] }],
          max_lifetime_days: 90,
          max_active_per_user: 10,
        }
      : route.request().method() === 'POST'
        ? {
            ...route.request().postDataJSON(),
            id: 'token-identity',
            prefix: 'ffk_fixture',
            created_at: '2026-10-28T00:00:00Z',
            revoked_at: null,
            last_used_at: null,
            token: 'synthetic-identity-private-secret',
          }
        : { items: [], total: 0, page: 1, page_size: 25, pages: 0 };
    await route.fulfill({
      status: route.request().method() === 'POST' ? 201 : 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
  await page.goto('/elements/?host=retained');
  await page.waitForFunction(() => !!customElements.get('firefly-koinon'));
  const bind = () =>
    page.evaluate(async () => {
      const sdk = await import('/sdk/index.js');
      const element = document.querySelector('firefly-koinon') as HTMLElement & {
        client: unknown;
        tenantId: string;
        showNavigation: boolean;
        accountSection: string;
      };
      element.tenantId = 'tenant-one';
      element.showNavigation = true;
      element.accountSection = 'tokens';
      element.client = new sdk.KoinonClient({
        transport: new sdk.FetchTransport({
          baseUrl: '/bff/api/v1',
          credentials: 'include',
          csrfToken: () => 'synthetic-csrf+token',
        }),
      });
    });
  await bind();
  await page.getByRole('button', { name: 'Create a token', exact: true }).click();
  await page.getByRole('textbox', { name: 'Token name', exact: true }).fill('Identity fixture');
  await page.getByRole('checkbox', { name: 'Read library', exact: true }).check();
  await page.getByRole('button', { name: 'Create a token', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'New API token', exact: true })).toHaveValue(
    'synthetic-identity-private-secret',
  );
  await bind();
  await expect(page.getByRole('textbox', { name: 'New API token', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Create a token', exact: true })).toBeVisible();
  await expect(page).toHaveURL('/elements/?host=retained');
});

for (const width of [1440, 390])
  test(`Spanish account page content and revoke state ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setup(page);
    await page.route('**/bff/api/v1/profile', (route) =>
      route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          subject: 'synthetic.reviewer',
          display_name: 'Alex Rivera',
          locale: 'es-ES',
          time_zone: 'Europe/Madrid',
          response_language: 'es',
          avatar_version: null,
        }),
      }),
    );
    await page.goto('/account/applications');
    await expect(
      page.getByText(
        'Los permisos también dependen de tu acceso actual a la organización y al espacio de trabajo.',
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Aplicaciones autorizadas', exact: true }),
    ).toBeVisible();
    await capture(page, `account-spanish-${width}`);
    const row = page.locator('.application-row').filter({ hasText: 'Research desktop' });
    await row.getByRole('button', { name: 'Consultar permisos', exact: true }).click();
    await row.getByRole('button', { name: 'Revocar acceso', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: '¿Revocar acceso?', exact: true }),
    ).toBeFocused();
    await capture(page, `account-spanish-revoke-${width}`);
  });

test('retrying a failed URL bootstrap restores the requested screen', async ({ page }) => {
  await mockService(page, { error: true });
  await page.goto('/settings');
  await expect(page.getByRole('alert')).toContainText('Catalog database is unavailable');
  await page.unroute('**/bff/api/v1/**');
  await mockService(page);
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page).toHaveURL('/settings');
  await expect(
    page.getByRole('navigation', { name: 'Settings sections', exact: true }),
  ).toBeVisible();
});

test('sign-in returns to the public account route for the current identity without retaining address data', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 1000 });
  const fixture = await setup(page);
  let authenticated = false;
  await page.route('**/bff/api/v1/context', (route) =>
    route.fulfill({
      status: authenticated ? 200 : 401,
      contentType: 'application/json',
      body: JSON.stringify(
        authenticated
          ? { ...fixtureContext, subject: 'current.identity' }
          : { detail: 'Sign in is required', code: 'UNAUTHENTICATED' },
      ),
    }),
  );
  await page.route('**/bff/api/v1/profile', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        subject: 'current.identity',
        display_name: 'Current identity',
        locale: 'en-US',
        time_zone: 'UTC',
        response_language: 'en',
        avatar_version: null,
      }),
    }),
  );
  await page.addInitScript(() =>
    Object.assign(window, {
      __savedPublicNavigation: sessionStorage.getItem('koinon.pending-account-navigation'),
    }),
  );
  await page.route('**/oauth2/authorization/koinon', (route) =>
    route.fulfill({ status: 302, headers: { location: '/' }, body: '' }),
  );
  await page.goto('/account/applications?retained=one#panel=two');
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
  fixture.rows[0].name = 'Current identity connection';
  authenticated = true;
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL('/account/applications');
  await expect(
    page.getByRole('heading', { name: 'Authorized applications', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Current identity connection', { exact: true })).toBeVisible();
  const saved = await page.evaluate(
    () => (window as Window & { __savedPublicNavigation: string }).__savedPublicNavigation,
  );
  expect(JSON.parse(saved)).toEqual({ view: 'library', accountSection: 'applications' });
  expect(
    await page.evaluate(() => sessionStorage.getItem('koinon.pending-account-navigation')),
  ).toBe(null);
  await capture(page, 'account-login-return-390');
});
