// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { expect, test, type Page } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService } from './fixtures';

const capabilities = {
  accounts_available: true,
  inbound_only: true,
  synchronization_available: true,
  providers: [
    {
      provider: 'google_drive',
      display_name: 'Google Drive',
      consent_available: true,
      unavailable_reason: null,
    },
  ],
  modes: ['document', 'dataset'],
  formats: [
    { extension: '.pdf', mode: 'document' },
    { extension: '.csv', mode: 'dataset' },
  ],
  schedule: {
    min_interval_seconds: 900,
    max_interval_seconds: 604800,
    calendar_timezones: 'iana',
    max_calendar_weekdays: 7,
  },
};
const account = {
  id: 'account',
  provider: 'google_drive',
  status: 'connected',
  revision: 1,
  account: {
    provider: 'google_drive',
    subject: 'PRIVATE_PROVIDER_SUBJECT',
    tenant_id: 'PRIVATE_PROVIDER_TENANT',
  },
  display_name: 'Research and governance — international operations',
  display_address: 'research.operations@example.test',
  display_address_verified: true,
  synchronization_available: true,
};
const root = {
  item_id: 'root',
  name: 'Policies for international research operations',
  kind: 'folder',
  version: 'current',
  size_bytes: null,
  mime_type: 'folder',
  parents: [],
  can_download: null,
  modified_at: null,
};
const file = {
  ...root,
  item_id: 'file',
  name: 'Cross-border research and governance handbook.pdf',
  kind: 'file',
  size_bytes: null,
  mime_type: 'application/pdf',
};
const receipt = {
  operation_id: 'operation',
  receipt_id: 'receipt',
  action: 'review',
  mapping_id: 'mapping',
  policy_id: 'review',
  expected_policy_revision: null,
  result_policy_revision: 4,
  review_digest: 'digest',
  review_expires_at: '2099-01-01T00:00:00Z',
  disposition: 'reviewed',
};
const destination = {
  segments: [{ id: 'collection-one', kind: 'collection', name: 'Reference library' }],
};
async function service(page: Page, locale = 'en-US') {
  await mockService(page);
  await page.route('**/bff/api/v1/branding/defaults', (route) => route.fulfill({ json: {} }));
  await page.route('**/bff/api/v1/tenants/*/branding', (route) =>
    route.fulfill({
      json: { tenant_id: 'tenant-one', schema_version: 1, revision: 0, branding: {} },
    }),
  );
  await page.route('**/bff/api/v1/notifications/unread-count', (route) =>
    route.fulfill({ json: { unread: 0 } }),
  );
  await page.route('**/organization/people/me/presentation', (route) =>
    route.fulfill({
      json: {
        tenant_id: 'tenant-one',
        subject: 'synthetic.reviewer',
        status: 'not_configured',
        display_name: 'Alex Rivera',
      },
    }),
  );
  await page.route('**/bff/api/v1/profile', (route) =>
    route.fulfill({
      json: {
        subject: 'synthetic.reviewer',
        display_name: 'Alex Rivera',
        locale,
        time_zone: 'UTC',
        response_language: locale.startsWith('es') ? 'es' : 'en',
        avatar_url: null,
        avatar_version: null,
      },
    }),
  );
  const writes: { path: string; body: Record<string, unknown> }[] = [];
  let policy: Record<string, unknown> | null = null;
  let active = false;
  let started = false;
  await page.route('**/content-sources/**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname.split('/content-sources')[1];
    if (request.method() === 'POST') writes.push({ path, body: request.postDataJSON() });
    if (path === '/capabilities') return route.fulfill({ json: capabilities });
    if (path === '/connections')
      return route.fulfill({
        json: { items: [account], next_cursor: null, synchronization_available: true },
      });
    if (path === '/reader-selection')
      return route.fulfill({ json: { revision: 1, connections: [] } });
    if (path.endsWith('/drives'))
      return route.fulfill({
        json: {
          items: [{ id: 'drive', name: 'Research shared drive', kind: 'drive' }],
          next_cursor: null,
        },
      });
    if (path.endsWith('/children'))
      return route.fulfill({ json: { folder: root, items: [file], next_cursor: null } });
    if (path === '/mapping-validations' || path.startsWith('/mapping-validations/')) {
      const complete = path !== '/mapping-validations';
      return route.fulfill({
        json: {
          validation_id: 'validation',
          revision: complete ? 2 : 1,
          state: complete ? 'complete' : 'scanning',
          expires_at: '2099-01-01T00:00:00Z',
          continuation_token: complete ? null : 'continuation',
          enumeration_complete: complete,
          observed_count: null,
          total: null,
          manifest_sha256: complete ? 'manifest' : null,
          reason_code: null,
        },
      });
    }
    if (path === '/mappings/mapping/runs')
      return route.fulfill({ json: { items: [], next_cursor: null } });
    if (path === '/runs/run')
      return route.fulfill({
        json: {
          id: 'run',
          mapping_id: 'mapping',
          policy_revision: 4,
          control_revision: 10,
          status: 'running',
          stopping: false,
          retry_of_run_id: null,
          counters: {},
          enumeration_complete: false,
          created_at: '2026-11-11T00:00:00Z',
          finished_at: null,
          can_cancel: true,
          can_retry: false,
        },
      });
    if (path === '/runs/run/items')
      return route.fulfill({
        json: {
          items: [
            {
              id: 'work',
              object_id: 'object',
              generation: 1,
              remote_version: 'current',
              kind: 'file',
              name: file.name,
              relative_path: [file.name],
              status: 'processing',
              error_code: null,
              source_id: null,
              asset_id: null,
              attempt_id: 'attempt',
              updated_at: '2026-11-11T00:00:00Z',
            },
          ],
          next_cursor: null,
        },
      });
    if (path === '/mapping-reviews') {
      policy = request.postDataJSON();
      return route.fulfill({ json: receipt });
    }
    if (path === '/mapping-reviews/review/items')
      return route.fulfill({
        json: {
          review_id: 'review',
          policy_revision: 4,
          review_digest: 'digest',
          expires_at: '2099-01-01T00:00:00Z',
          items: [
            {
              ...file,
              filename: file.name,
              ancestry: [],
              relative_path: [file.name],
              action: 'create',
              reason: null,
              destination_relative_path: ['Policies', file.name],
              collision: 'none',
            },
          ],
          next_cursor: null,
          enumeration_complete: true,
          validation_id: 'validation',
          root_kind: 'folder',
          total: null,
          observed_count: null,
          known_bytes: null,
          unknown_size_count: null,
          can_apply: true,
          destination,
        },
      });
    if (path === '/mappings' && request.method() === 'POST') {
      active = true;
      return route.fulfill({ json: { ...receipt, action: 'apply', disposition: 'accepted' } });
    }
    if (path === '/mappings') return route.fulfill({ json: { items: [], next_cursor: null } });
    if (path === '/mappings/mapping/sync') {
      started = true;
      return route.fulfill({
        json: {
          operation_id: request.postDataJSON().operation_id,
          receipt_id: 'control',
          action: 'sync',
          control_revision: 10,
          run_id: 'run',
          disposition: 'queued',
        },
      });
    }
    if (path === '/mappings/mapping')
      return route.fulfill({
        json: {
          id: 'mapping',
          revision: 4,
          policy_revision: active ? 4 : null,
          latest_review_revision: 4,
          control_revision: started ? 10 : 9,
          connection_id: 'account',
          policy,
          status: 'active',
          next_run_at: null,
          can_pause: true,
          can_resume: false,
          can_retire: true,
          can_sync: active && !started,
          presentation: {
            source_root: { name: root.name, relative_path: [] },
            destination,
            unavailable_reason: null,
          },
        },
      });
    return route.fulfill({
      status: 404,
      json: { detail: 'No controlled source fixture matches this operation.' },
    });
  });
  return { writes };
}
async function capture(page: Page, name: string) {
  const directory = process.env['KOINON_E2E_CAPTURE_DIR'];
  if (!directory) return;
  await mkdir(directory, { recursive: true });
  await page.screenshot({ path: resolve(directory, name + '.png'), fullPage: true });
  const main = page.locator('ffk-shell main');
  const previous = await main.evaluate((element) => {
    const top = element.scrollTop;
    element.scrollTop = element.scrollHeight;
    return top;
  });
  await page.screenshot({ path: resolve(directory, name + '-end.png'), fullPage: true });
  await main.evaluate((element, top) => {
    element.scrollTop = top;
  }, previous);
}
for (const width of [1440, 390, 320])
  for (const theme of ['light', 'dark'] as const) {
    test(`source accounts and exact policy review at ${width}px ${theme}`, async ({ page }) => {
      const es = theme === 'dark',
        locale = es ? 'es-ES' : 'en-US';
      const t = (en: string, spanish: string) => (es ? spanish : en);
      const errors: string[] = [];
      page.on('pageerror', (error) => errors.push(error.message));
      page.on('console', (message) => {
        if (message.type() === 'error') errors.push(message.text());
      });
      await page.setViewportSize({ width, height: 1000 });
      await page.addInitScript((theme) => localStorage.setItem('koinon-theme', theme), theme);
      const api = await service(page, locale);
      await page.goto('/account/connected-sources');
      await expect(
        page.getByRole('heading', {
          name: t('Connected sources', 'Fuentes conectadas'),
          exact: true,
        }),
      ).toBeVisible();
      await expect(page.getByText(account.display_address, { exact: true })).toBeVisible();
      await expect(page.locator('body')).not.toContainText('PRIVATE_PROVIDER');
      await capture(page, `accounts-${width}-${theme}`);
      await page.goto('/library');
      if (width <= 390)
        await page
          .getByText(t('Library actions', 'Acciones de la biblioteca'), { exact: true })
          .click();
      await page
        .getByRole('button', { name: t('Synchronization', 'Sincronización'), exact: true })
        .click();
      await expect(page).toHaveURL(/\/library\/synchronization$/);
      await page
        .getByRole('button', {
          name: t('New synchronization', 'Nueva sincronización'),
          exact: true,
        })
        .click();
      await page
        .getByRole('combobox', { name: t('Connected account', 'Cuenta conectada'), exact: true })
        .selectOption('account');
      await page.getByRole('button', { name: 'Research shared drive', exact: true }).click();
      await page
        .getByRole('button', { name: t('Use this folder', 'Usar esta carpeta'), exact: true })
        .click();
      await capture(page, `content-${width}-${theme}`);
      await page.getByRole('button', { name: t('Continue', 'Continuar'), exact: true }).click();
      const workspace = page.getByRole('treeitem', { name: 'Research operations', exact: true });
      await workspace.focus();
      await page.keyboard.press('ArrowRight');
      const project = page.getByRole('treeitem', { name: 'Operations intelligence', exact: true });
      await project.focus();
      await page.keyboard.press('ArrowRight');
      const folder = page.getByRole('treeitem', { name: 'Reference library', exact: true });
      await folder.focus();
      await page.keyboard.press('Enter');
      await expect(
        page.getByText(t('Selected destination', 'Destino seleccionado'), { exact: true }),
      ).toBeVisible();
      await capture(page, `structure-${width}-${theme}`);
      await page.getByRole('button', { name: t('Continue', 'Continuar'), exact: true }).click();
      await page
        .getByRole('combobox', { name: t('Schedule', 'Programación'), exact: true })
        .selectOption('weekly');
      await page
        .getByLabel(t('IANA timezone', 'Zona horaria IANA'), { exact: true })
        .fill('Europe/Madrid');
      await page.getByLabel(t('Local time', 'Hora local'), { exact: true }).fill('09:30');
      await capture(page, `updates-${width}-${theme}`);
      await page
        .getByRole('button', {
          name: t('Review synchronization', 'Revisar sincronización'),
          exact: true,
        })
        .click();
      await expect(
        page.getByText(t('Preparation complete', 'Preparación completa'), { exact: true }),
      ).toBeVisible();
      await capture(page, `preparation-${width}-${theme}`);
      await page
        .getByRole('button', {
          name: t('Review prepared selection', 'Revisar selección preparada'),
          exact: true,
        })
        .click();
      await expect(
        page.getByText(t('Size unknown', 'Tamaño desconocido'), { exact: true }),
      ).toBeVisible();
      const approve = page.getByRole('button', {
        name: t('Approve synchronization', 'Aprobar sincronización'),
        exact: true,
      });
      await page.mouse.move(0, 0);
      const actionBackground = await approve.evaluate(
        (element) => getComputedStyle(element).backgroundColor,
      );
      await approve.hover();
      await expect(approve).toHaveCSS('background-color', actionBackground);
      await approve.focus();
      await expect(approve).toBeFocused();
      if (width <= 390) {
        const main = page.locator('ffk-shell main');
        await main.evaluate((element) => {
          element.scrollTop = element.scrollHeight;
        });
        await expect
          .poll(() =>
            main.evaluate(
              (element) => element.scrollHeight - element.clientHeight - element.scrollTop,
            ),
          )
          .toBeLessThanOrEqual(1);
        await page.evaluate(
          () =>
            new Promise<void>((resolve) =>
              requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
            ),
        );
        await expect(approve).toBeFocused();
        const geometry = await page.locator('ffk-synchronization-page').evaluate((element) => {
          const approve = element.querySelector<HTMLElement>('.wizard-main button.primary')!;
          const back = element.querySelector<HTMLElement>('.wizard-main > .actions button')!;
          const future = approve.previousElementSibling!;
          const root = element.getRootNode() as ShadowRoot;
          const main = root.querySelector('ffk-shell main')!;
          const footer = root.querySelector('ffk-shell footer')!;
          const rect = (node: Element) => {
            const box = node.getBoundingClientRect();
            return { top: box.top, bottom: box.bottom, height: box.height };
          };
          return {
            main: rect(main),
            footer: rect(footer),
            future: rect(future),
            approve: rect(approve),
            back: rect(back),
            approvePosition: getComputedStyle(approve).position,
            actionsPosition: getComputedStyle(back.parentElement!).position,
          };
        });
        expect(geometry.future.bottom).toBeLessThanOrEqual(geometry.approve.top);
        expect(geometry.approve.bottom).toBeLessThanOrEqual(geometry.back.top);
        expect(geometry.approve.top).toBeGreaterThanOrEqual(geometry.main.top);
        expect(geometry.back.bottom).toBeLessThanOrEqual(geometry.main.bottom);
        expect(geometry.back.bottom).toBeLessThanOrEqual(geometry.footer.top);
        await page.keyboard.press('Tab');
        await expect(
          page.getByRole('button', { name: t('Back', 'Atrás'), exact: true }),
        ).toBeFocused();
        await page.keyboard.press('Shift+Tab');
        await expect(approve).toBeFocused();
        const directory = process.env['KOINON_E2E_CAPTURE_DIR'];
        if (directory) {
          await mkdir(directory, { recursive: true });
          await writeFile(
            resolve(directory, `review-geometry-${width}-${theme}.json`),
            JSON.stringify(geometry, null, 2),
          );
        }
        console.log(`review geometry ${width} ${theme}: ${JSON.stringify(geometry)}`);
      }
      await expect(page.locator('ffk-synchronization-page')).not.toContainText(
        t('Items reviewed:', 'Elementos revisados:'),
      );
      await expect(page.locator('ffk-synchronization-page')).not.toContainText(
        t('Known size:', 'Tamaño conocido:'),
      );
      await capture(page, `review-${width}-${theme}`);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      if (width === 1440) {
        await page.evaluate(() => (document.documentElement.style.zoom = '2'));
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
          true,
        );
        await capture(page, `review-${width}-${theme}-zoom200`);
        await page.evaluate(() => (document.documentElement.style.zoom = '1'));
      }
      await approve.click();
      await expect(
        page.getByRole('button', { name: t('Sync now', 'Sincronizar ahora'), exact: true }),
      ).toBeVisible();
      expect(api.writes.some((row) => row.path.endsWith('/sync'))).toBe(false);
      await page
        .getByRole('button', { name: t('Sync now', 'Sincronizar ahora'), exact: true })
        .click();
      await expect
        .poll(() => api.writes.map((row) => row.path))
        .toEqual([
          '/mapping-validations',
          '/mapping-validations/validation/continue',
          '/mapping-reviews',
          '/mappings',
          '/mappings/mapping/sync',
        ]);
      expect(api.writes[0].body).toMatchObject({
        root_id: 'root',
        destination: { parent_id: 'collection-one' },
        schedule: { kind: 'calendar', timezone: 'Europe/Madrid', time: '09:30', weekdays: [1] },
      });
      expect(api.writes[3].body).toMatchObject({
        expected_revision: 4,
        review_id: 'review',
        review_digest: 'digest',
      });
      expect(api.writes[4].body).toMatchObject({ expected_revision: 9 });
      await expect(
        page.getByText(
          t(
            'Only searchable items are ready for answers.',
            'Solo los elementos disponibles para búsqueda están listos para responder.',
          ),
          { exact: true },
        ),
      ).toBeVisible();
      await capture(page, `run-${width}-${theme}`);
      await page.reload();
      expect(api.writes).toHaveLength(5);
      expect(errors).toEqual([]);
    });
  }
test('synchronization code remains lazy and account errors retain no protected rows', async ({
  page,
}) => {
  const scripts: Promise<string>[] = [];
  page.on('response', (response) => {
    if (response.request().resourceType() === 'script') scripts.push(response.text());
  });
  await service(page);
  await page.goto('/library');
  await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  expect((await Promise.all(scripts)).some((text) => text.includes('ffk-source-browser'))).toBe(
    false,
  );
  await page.route('**/content-sources/connections?**', (route) =>
    route.fulfill({ status: 403, json: { detail: 'Denied' } }),
  );
  await page.goto('/account/connected-sources');
  await expect(page.getByRole('alert')).toContainText('Access changed');
  await expect(page.locator('body')).not.toContainText(account.display_name);
});

for (const validState of [true, false]) {
  test(`source consent requires registered callback and matching state: ${validState}`, async ({
    page,
    context,
  }) => {
    await service(page);
    const completed: unknown[] = [];
    let connected = false;
    await page.route('**/content-sources/connections?**', (route) =>
      route.fulfill({
        json: {
          items: connected ? [account] : [],
          next_cursor: null,
          synchronization_available: true,
        },
      }),
    );
    await page.route('**/content-sources/authorizations', (route) =>
      route.fulfill({
        json: {
          connection_id: 'account',
          challenge_id: 'challenge',
          callback_uri: 'http://127.0.0.1:18782/source-callback',
          authorization_url: 'http://127.0.0.1:18782/provider-consent?state=expected-state',
          expires_at: '2099-01-01T00:00:00Z',
        },
      }),
    );
    await page.route('**/content-sources/authorizations/complete', (route) => {
      completed.push(route.request().postDataJSON());
      connected = true;
      return route.fulfill({ json: account });
    });
    await context.route('**/provider-consent?**', (route) =>
      route.fulfill({
        contentType: 'text/html',
        body: '<!doctype html><title>Provider consent</title><p>Choose an account.</p>',
      }),
    );
    await context.route('**/source-callback?**', (route) =>
      route.fulfill({
        contentType: 'text/html',
        body: '<!doctype html><title>Returning to Koinon</title>',
      }),
    );
    await page.goto('/account/connected-sources');
    await page.getByRole('button', { name: 'Connect account: Google Drive', exact: true }).click();
    await expect(
      page.getByText('Continue to Google Drive to choose your account and allow read access.', {
        exact: true,
      }),
    ).toBeVisible();
    const opened = page.waitForEvent('popup');
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    const popup = await opened;
    await popup.waitForURL('**/provider-consent?state=expected-state');
    await popup.goto(
      'http://127.0.0.1:18782/source-callback?code=one-time-code&state=' +
        (validState ? 'expected-state' : 'wrong-state'),
      { waitUntil: 'commit' },
    );
    if (validState) {
      await expect(page.getByText('Account connected.', { exact: true })).toBeVisible();
      expect(completed).toEqual([
        { challenge_id: 'challenge', state: 'expected-state', code: 'one-time-code' },
      ]);
      await expect(page.getByText(account.display_address, { exact: true })).toBeVisible();
    } else {
      await expect(page.getByRole('alert')).toContainText(
        'Account connection could not be verified',
      );
      expect(completed).toEqual([]);
    }
  });
}
test('account loading, empty continuation, and a late old-organization page keep protected names out', async ({
  page,
}) => {
  await service(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  let requested = false;
  await page.route('**/content-sources/connections?**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.includes('tenant-two'))
      return route.fulfill({ json: { items: [], next_cursor: null } });
    if (!url.searchParams.has('cursor'))
      return route.fulfill({ json: { items: [], next_cursor: 'continue' } });
    requested = true;
    await gate;
    return route.fulfill({ json: { items: [account], next_cursor: null } });
  });
  await page.goto('/account/connected-sources');
  await expect(page.getByText('No matching items on this page.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Continue browsing', exact: true }).click();
  await expect.poll(() => requested).toBe(true);
  await expect(page.getByText('Loading accounts…', { exact: true })).toBeVisible();
  await capture(page, 'accounts-loading-1440-light');
  await page
    .getByRole('combobox', { name: 'Organization', exact: true })
    .selectOption('tenant-two');
  release();
  await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  await expect(page.locator('body')).not.toContainText(account.display_name);
  await page.goto('/account/connected-sources');
  await expect(page.getByText('No matching items.', { exact: true })).toBeVisible();
  await expect(page.locator('body')).not.toContainText(account.display_name);
  await capture(page, 'accounts-empty-1440-light');
});

async function prepareSourceReview(page: Page, es = false, review = true, fileRoot = false) {
  const t = (en: string, spanish: string) => (es ? spanish : en);
  await page.goto('/library/synchronization');
  await page
    .getByRole('button', { name: t('New synchronization', 'Nueva sincronización'), exact: true })
    .click();
  await page
    .getByRole('combobox', { name: t('Connected account', 'Cuenta conectada'), exact: true })
    .selectOption('account');
  await page.getByRole('button', { name: 'Research shared drive', exact: true }).click();
  await page
    .getByRole('button', {
      name: fileRoot
        ? t('Select', 'Seleccionar') + ': ' + file.name
        : t('Use this folder', 'Usar esta carpeta'),
      exact: true,
    })
    .click();
  await page.getByRole('button', { name: t('Continue', 'Continuar'), exact: true }).click();
  for (const name of ['Research operations', 'Operations intelligence']) {
    await page.getByRole('treeitem', { name, exact: true }).focus();
    await page.keyboard.press('ArrowRight');
  }
  await page.getByRole('treeitem', { name: 'Reference library', exact: true }).focus();
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: t('Continue', 'Continuar'), exact: true }).click();
  await page
    .getByRole('button', {
      name: t('Review synchronization', 'Revisar sincronización'),
      exact: true,
    })
    .click();
  if (review)
    await page
      .getByRole('button', {
        name: es ? 'Revisar selección preparada' : 'Review prepared selection',
        exact: true,
      })
      .click();
}
test('conflicted Spanish review keeps approval disabled and exposes actual destination paths', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 1000 });
  await page.addInitScript(() => localStorage.setItem('koinon-theme', 'dark'));
  const api = await service(page, 'es-ES');
  await page.route('**/mapping-reviews/review/items?**', (route) =>
    route.fulfill({
      json: {
        review_id: 'review',
        policy_revision: 4,
        review_digest: 'digest',
        expires_at: '2099-01-01T00:00:00Z',
        items: [
          {
            ...file,
            filename: file.name,
            ancestry: [],
            relative_path: ['Source folder', file.name],
            action: 'create',
            reason: null,
            destination_relative_path: ['Conflicting folder', file.name],
            collision: 'destination_name',
          },
        ],
        next_cursor: null,
        enumeration_complete: true,
        total: 1,
        observed_count: 1,
        known_bytes: 0,
        unknown_size_count: 1,
        can_apply: false,
        destination,
      },
    }),
  );
  await prepareSourceReview(page, true);
  await expect(
    page.getByRole('button', { name: 'Aprobar sincronización', exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText('Ya existe un elemento en esta ruta de destino.', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Conflicting folder / ' + file.name, { exact: true })).toBeVisible();
  expect(api.writes.map((row) => row.path)).toEqual([
    '/mapping-validations',
    '/mapping-validations/validation/continue',
    '/mapping-reviews',
  ]);
  await capture(page, 'conflict-390-dark-es');
});
test('lost approval checks its receipt and requires a fresh explicit start', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await service(page);
  const approvals: Record<string, unknown>[] = [];
  let syncs = 0;
  await page.route('**/content-sources/mappings', (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    approvals.push(route.request().postDataJSON());
    return route.abort('failed');
  });
  await page.route('**/content-sources/mappings/mapping/operations/**', (route) =>
    route.fulfill({
      json: {
        kind: 'policy',
        receipt: {
          ...receipt,
          operation_id: approvals[0]['operation_id'],
          action: 'apply',
          disposition: 'accepted',
        },
      },
    }),
  );
  await page.route('**/content-sources/mappings/mapping', (route) =>
    route.fulfill({
      json: {
        id: 'mapping',
        revision: 4,
        policy_revision: 4,
        latest_review_revision: 4,
        control_revision: 9,
        connection_id: 'account',
        policy: {
          connection_id: 'account',
          drive_id: 'drive',
          root_id: 'root',
          destination: { parent_id: 'collection-one' },
          hierarchy: 'preserve',
          mode: 'document',
          formats: ['.pdf'],
          excluded_ids: [],
          recursive: true,
          schedule: { kind: 'manual' },
          removal_policy: 'pause_for_review',
          schema_version: 1,
        },
        status: 'active',
        next_run_at: null,
        can_pause: true,
        can_resume: false,
        can_retire: true,
        can_sync: true,
        presentation: {
          source_root: { name: root.name, relative_path: [] },
          destination,
          unavailable_reason: null,
        },
      },
    }),
  );
  await page.route('**/content-sources/mappings/mapping/sync', (route) => {
    syncs++;
    return route.fallback();
  });
  await prepareSourceReview(page);
  await page.getByRole('button', { name: 'Approve synchronization', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Approval result is unknown');
  await expect(
    page.getByRole('button', { name: 'Approve synchronization', exact: true }),
  ).toBeDisabled();
  await capture(page, 'approval-unknown-1440-light');
  await page.getByRole('button', { name: 'Check request', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sync now', exact: true })).toBeVisible();
  expect(approvals).toHaveLength(1);
  expect(syncs).toBe(0);
  const pause = page.getByRole('button', { name: 'Pause synchronization', exact: true });
  await pause.click();
  await expect(
    page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }),
  ).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(pause).toBeFocused();
  await capture(page, 'approval-recovered-1440-light');
  await page.reload();
  expect(approvals).toHaveLength(1);
  expect(syncs).toBe(0);
});

test('cancelling while consent begins discards its late response and closes the window', async ({
  page,
  context,
}) => {
  await service(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  await page.route('**/content-sources/authorizations', async (route) => {
    await gate;
    return route.fulfill({
      json: {
        connection_id: 'account',
        challenge_id: 'challenge',
        callback_uri: 'http://127.0.0.1:18782/source-callback',
        authorization_url: 'http://127.0.0.1:18782/provider-consent?state=expected',
        expires_at: '2099-01-01T00:00:00Z',
      },
    });
  });
  await page.goto('/account/connected-sources');
  await page.getByRole('button', { name: 'Connect account: Google Drive', exact: true }).click();
  const response = page.waitForResponse('**/content-sources/authorizations');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(page.getByText('Waiting for account connection…', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  release();
  await response;
  await expect(
    page.getByText('Account connection was cancelled. No synchronization was created.', {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText('Waiting for account connection…', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Open sign-in', exact: true })).toHaveCount(0);
  await expect.poll(() => context.pages().length).toBe(1);
});
test('expired review cannot approve and keeps refresh explicit', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 1000 });
  const api = await service(page);
  await page.route('**/mapping-reviews/review/items?**', (route) =>
    route.fulfill({
      json: {
        review_id: 'review',
        policy_revision: 4,
        review_digest: 'digest',
        expires_at: '2000-01-01T00:00:00Z',
        items: [],
        next_cursor: null,
        enumeration_complete: true,
        total: 0,
        observed_count: 0,
        known_bytes: 0,
        unknown_size_count: 0,
        can_apply: true,
        destination,
      },
    }),
  );
  await prepareSourceReview(page);
  await expect(
    page.getByRole('button', { name: 'Approve synchronization', exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole('button', { name: 'Review prepared selection', exact: true }),
  ).toBeEnabled();
  expect(api.writes.map((row) => row.path)).toEqual([
    '/mapping-validations',
    '/mapping-validations/validation/continue',
    '/mapping-reviews',
  ]);
  await capture(page, 'review-expired-390-light');
});

test('lost continuation reloads status without replay and requires explicit resume', async ({
  page,
}) => {
  const api = await service(page);
  let continuations = 0;
  const preparation = (complete = false) => ({
    validation_id: 'validation',
    revision: continuations + 1,
    state: complete ? 'complete' : 'verifying',
    expires_at: '2099-01-01T00:00:00Z',
    continuation_token: complete ? null : 'next-token',
    enumeration_complete: complete,
    observed_count: null,
    total: null,
    manifest_sha256: complete ? 'manifest' : null,
    reason_code: null,
  });
  await page.route('**/mapping-validations/validation/continue', (route) => {
    continuations++;
    return continuations === 1 ? route.abort('failed') : route.fulfill({ json: preparation(true) });
  });
  await page.route('**/mapping-validations/validation', (route) =>
    route.fulfill({ json: preparation() }),
  );
  await prepareSourceReview(page, false, false);
  await expect(page.getByRole('button', { name: 'Check request', exact: true })).toBeVisible();
  await capture(page, 'preparation-unknown');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Resume preparation', exact: true })).toBeVisible();
  expect(continuations).toBe(1);
  await expect(
    page.getByRole('button', { name: 'Approve synchronization', exact: true }),
  ).toHaveCount(0);
  await page.getByRole('button', { name: 'Resume preparation', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Review prepared selection', exact: true }),
  ).toBeVisible();
  expect(continuations).toBe(2);
  expect(api.writes.filter((row) => row.path === '/mapping-validations')).toHaveLength(1);
  const retained = await page.evaluate(() => sessionStorage.getItem('koinon-source-recovery'));
  expect(retained).not.toContain('next-token');
  expect(retained).not.toContain('Research');
  await capture(page, 'preparation-resumed');
});

test('a later-page preparation collision blocks review and exposes selection corrections', async ({
  page,
}) => {
  await service(page);
  let slices = 0;
  await page.route('**/mapping-validations/validation/continue', (route) => {
    slices++;
    return route.fulfill({
      json: {
        validation_id: 'validation',
        revision: slices + 1,
        state: slices === 2 ? 'blocked' : 'scanning',
        expires_at: '2099-01-01T00:00:00Z',
        continuation_token: slices === 2 ? null : 'second-page',
        enumeration_complete: slices === 2,
        observed_count: null,
        total: null,
        manifest_sha256: null,
        reason_code: slices === 2 ? 'SOURCE_NAME_COLLISION' : null,
      },
    });
  });
  await prepareSourceReview(page, false, false);
  await expect(
    page.getByText('Source files resolve to the same destination path.', { exact: true }),
  ).toBeVisible();
  expect(slices).toBe(2);
  await expect(
    page.getByRole('button', { name: 'Review prepared selection', exact: true }),
  ).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Edit selection', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Change destination', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Abandon preparation', exact: true }).click();
  await expect(
    page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }),
  ).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(
    page.getByRole('button', { name: 'Abandon preparation', exact: true }),
  ).toBeFocused();
  await capture(page, 'preparation-blocked');
});

test('a file root disables recursion and sends no sibling exclusions', async ({ page }) => {
  const api = await service(page);
  await prepareSourceReview(page, false, true, true);
  expect(api.writes[0].body).toMatchObject({ root_id: 'file', recursive: false, excluded_ids: [] });
  await expect(
    page.getByRole('button', { name: 'Approve synchronization', exact: true }),
  ).toBeEnabled();
});

test('denial on a later review page removes prior authorized names and totals', async ({
  page,
}) => {
  await service(page);
  await page.route('**/mapping-reviews/review/items?**', (route) => {
    if (new URL(route.request().url()).searchParams.has('cursor'))
      return route.fulfill({ status: 403, json: { detail: 'Access changed' } });
    return route.fulfill({
      json: {
        review_id: 'review',
        validation_id: 'validation',
        root_kind: 'folder',
        policy_revision: 4,
        review_digest: 'digest',
        expires_at: '2099-01-01T00:00:00Z',
        items: [
          {
            ...file,
            name: 'CURRENT_AUTHORIZED_NAME.pdf',
            filename: 'CURRENT_AUTHORIZED_NAME.pdf',
            ancestry: [],
            relative_path: ['CURRENT_AUTHORIZED_NAME.pdf'],
            destination_relative_path: ['CURRENT_AUTHORIZED_NAME.pdf'],
            action: 'create',
            collision: 'none',
            reason: null,
          },
        ],
        next_cursor: 'second',
        enumeration_complete: true,
        total: null,
        observed_count: null,
        known_bytes: null,
        unknown_size_count: null,
        can_apply: true,
        destination,
      },
    });
  });
  await prepareSourceReview(page);
  await expect(page.locator('ffk-synchronization-page')).toContainText(
    'CURRENT_AUTHORIZED_NAME.pdf',
  );
  await page.getByRole('button', { name: 'Continue browsing', exact: true }).click();
  await expect(page.locator('ffk-synchronization-page')).not.toContainText(
    'CURRENT_AUTHORIZED_NAME.pdf',
  );
  await expect(page.locator('ffk-synchronization-page')).not.toContainText(root.name);
  await expect(
    page.getByRole('button', { name: 'Approve synchronization', exact: true }),
  ).toHaveCount(0);
});
