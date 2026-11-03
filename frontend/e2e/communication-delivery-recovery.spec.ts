// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled requests qualify the compiled journey, not external email delivery.
import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockService, context, openAdministration } from './fixtures';
async function fixture(page: Page) {
  await mockService(page);
  let failed = false,
    generation = 4;
  const writes: { path: string; body: unknown; key: string | undefined }[] = [];
  const original = {
    id: 'original',
    kind: 'welcome',
    recipient_display: 'Alex Rivera',
    scope_name: 'Knowledge operations',
    status: 'unknown',
    created_at: '2026-11-01T10:00:00Z',
    last_attempt_at: '2026-11-01T10:00:01Z',
    next_attempt_at: null,
    attempt_count: 1,
    failure_code: null,
    safe_explanation: 'Submission may have occurred. Its outcome is unknown.',
    can_retry: false,
  };
  const observation = {
    id: 'observation',
    delivery_id: 'original',
    source: 'operation_lookup',
    operation_state: 'accepted',
    recipient_state: 'not_observed',
    checked_at: '2026-11-02T10:00:00Z',
    reason_code: null,
  };
  let observed = false,
    denied = false;
  let queued = 0;
  let readCount = 0,
    readFailure = 0;
  let accepted: { key: string | undefined; body: unknown } | null = null;
  await page.route('**/bff/api/v1/**', async (route) => {
    const req = route.request(),
      path = new URL(req.url()).pathname.replace('/bff/api/v1', ''),
      method = req.method();
    const json = (value: unknown, status = 200) => route.fulfill({ status, json: value });
    if (path === '/context')
      return json({
        ...context,
        memberships: [
          {
            id: 'admin',
            subject: context.subject,
            tenant_id: 'tenant-one',
            workspace_id: null,
            role: 'admin',
            active: true,
          },
        ],
        tenants: context.tenants.map((t) => ({
          ...t,
          permissions: [...t.permissions, 'members:write'],
        })),
      });
    if (!path.includes('/communications/')) return route.fallback();
    if (method === 'GET') {
      ++readCount;
      if (readFailure) return json({ code: 'UNAVAILABLE' }, readFailure);
    }
    if (method === 'POST')
      writes.push({ path, body: req.postDataJSON(), key: req.headers()['idempotency-key'] });
    if (path.endsWith('/capabilities'))
      return json({
        state: 'ready',
        provider_label: 'Configured email service',
        sender_name: 'Knowledge operations',
        sender_address: 'notifications@example.test',
        reply_to: null,
        public_address_configured: true,
        issues: [],
      });
    if (path.endsWith('/policy'))
      return json({ revision: 1, rules: [], digest_enabled: false, can_update: true });
    if (path.endsWith('/deliveries'))
      return json({ items: [original], page: 1, page_size: 25, total: 1, pages: 1 });
    if (denied && path.includes('/deliveries/'))
      return json({ code: 'ACCESS_DENIED', detail: 'Private provider exception' }, 403);
    if (path.endsWith('/recovery'))
      return json({
        delivery_id: path.includes('/new-welcome/') ? 'new-welcome' : 'original',
        generation,
        submission_status: 'unknown',
        attempt_count: 1,
        can_inspect: !path.includes('/new-welcome/'),
        inspection_reason: null,
        provider_binding_state: 'verified',
        can_recover_welcome: !path.includes('/new-welcome/'),
        recovery_reason: null,
        contact_id: 'approved-contact',
        contact_revision: 3,
        possible_original_late_arrival: true,
      });
    if (path.endsWith('/observations')) {
      if (method === 'POST') {
        observed = true;
        return json(observation);
      }
      return json({ items: observed ? [observation] : [], has_more: false });
    }
    if (path.endsWith('/welcome-recovery')) {
      if (accepted) {
        expect(req.headers()['idempotency-key']).toBe(accepted.key);
        expect(req.postDataJSON()).toEqual(accepted.body);
      } else {
        accepted = { key: req.headers()['idempotency-key'], body: req.postDataJSON() };
        queued++;
        generation++;
      }
      if (failed) return route.abort('failed');
      return json({
        original_delivery_id: 'original',
        delivery_id: 'new-welcome',
        status: 'queued',
        possible_original_late_arrival: true,
      });
    }
    if (path.endsWith('/new-welcome'))
      return json({ ...original, id: 'new-welcome', status: 'queued', attempt_count: 0 });
    if (path.endsWith('/original')) return json(original);
    return json({ code: 'UNEXPECTED_ROUTE' }, 404);
  });
  return {
    writes,
    reads: () => readCount,
    status: (status: string) => {
      original.status = status;
    },
    readFailure: (status: number) => {
      readFailure = status;
    },
    deny: () => {
      denied = true;
    },
    queued: () => queued,
    fail: (value: boolean) => {
      failed = value;
    },
    changed: () => {
      generation++;
    },
  };
}
async function open(page: Page, width: number, pending = false) {
  await page.goto('/library');
  if (width < 700) await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  await openAdministration(page, 'Settings');
  if (width < 700)
    await page
      .getByRole('combobox', { name: 'Settings section', exact: true })
      .selectOption('communications');
  else await page.getByRole('button', { name: 'Communications', exact: true }).click();
  const admin = page.locator('ffk-communications-admin');
  await admin.getByRole('button', { name: 'Delivery history', exact: true }).click();
  await admin.getByRole('button', { name: 'Details', exact: true }).click();
  const child = admin.locator('ffk-delivery-recovery');
  await expect(
    child.getByRole('heading', { name: 'Email service and receipt', exact: true }),
  ).toBeVisible();
  await expect(
    child.getByRole('button', {
      name: pending ? 'Review saved request' : 'Check email service',
      exact: true,
    }),
  ).toBeEnabled();
  return { admin, child };
}
async function capture(page: Page, name: string) {
  const dir = process.env['KOINON_DELIVERY_RECOVERY_SCREENSHOTS'];
  if (dir) {
    await mkdir(dir, { recursive: true });
    await page.screenshot({ path: `${dir}/${name}.png` });
  }
}
for (const width of [1440, 390])
  test(`inspects existing provider operation and reviews a separate new welcome at ${width}px`, async ({
    page,
  }) => {
    const service = await fixture(page);
    await page.setViewportSize({ width, height: 1100 });
    const { admin, child } = await open(page, width);
    expect(service.writes).toHaveLength(0);
    await child.getByRole('button', { name: 'Check email service', exact: true }).click();
    const review = child.getByRole('region', { name: 'Review delivery action', exact: true });
    await expect(
      review.getByRole('heading', { name: 'Check email service', exact: true }),
    ).toBeFocused();
    await review.getByRole('button', { name: 'Check email service', exact: true }).click();
    await expect(child).toContainText('does not confirm that the recipient received');
    await expect(admin.locator('.delivery-detail')).toContainText('Outcome unknown');
    expect(service.writes).toHaveLength(1);
    await expect(
      child.getByRole('button', { name: 'Refresh recorded checks', exact: true }),
    ).toHaveCount(0);
    await expect(
      child.getByRole('button', { name: 'Send a new welcome', exact: true }),
    ).toBeEnabled();
    await child.getByRole('button', { name: 'Send a new welcome', exact: true }).click();
    const welcome = child.getByRole('region', { name: 'Review delivery action', exact: true });
    const confirm = welcome.getByRole('button', { name: 'Queue new welcome', exact: true });
    await expect(confirm).toBeDisabled();
    await expect(welcome).toContainText('Alex Rivera');
    await welcome.getByRole('checkbox').check();
    await confirm.scrollIntoViewIfNeeded();
    await capture(page, `welcome-review-${width}`);
    await confirm.click();
    await expect(child).toContainText('The earlier delivery is unchanged and may still arrive');
    await expect(child).not.toContainText('Delivered');
    await expect(
      child.getByRole('button', { name: 'View new welcome', exact: true }),
    ).toBeVisible();
    expect(service.writes).toHaveLength(2);
    expect(service.writes[1].body).toEqual({
      expected_generation: 4,
      contact_id: 'approved-contact',
      expected_contact_revision: 3,
      reason: 'recipient_reported_not_received',
      acknowledge_possible_duplicate: true,
    });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await capture(page, `welcome-acknowledged-${width}`);
    await child.getByRole('button', { name: 'View new welcome', exact: true }).click();
    await expect(admin.locator('.delivery-detail')).toContainText('Queued');
    await expect(
      child.getByRole('button', { name: 'Send a new welcome', exact: true }),
    ).toHaveCount(0);
    expect(service.queued()).toBe(1);
  });
test('unknown welcome submission retains one request and reload does not send it again', async ({
  page,
}) => {
  const service = await fixture(page);
  service.fail(true);
  let { child } = await open(page, 1440);
  await child.getByRole('button', { name: 'Send a new welcome', exact: true }).click();
  let review = child.getByRole('region', { name: 'Review delivery action', exact: true });
  await review.getByRole('checkbox').check();
  await review.getByRole('button', { name: 'Queue new welcome', exact: true }).click();
  await expect(child).toContainText('request result is not confirmed');
  const first = service.writes[0];
  await page.reload();
  ({ child } = await open(page, 1440, true));
  expect(service.writes).toHaveLength(1);
  await child.getByRole('button', { name: 'Review saved request', exact: true }).click();
  review = child.getByRole('region', { name: 'Review delivery action', exact: true });
  await expect(review).toContainText('exact saved request');
  service.changed();
  service.fail(false);
  await review.getByRole('checkbox').check();
  await review.getByRole('button', { name: 'Queue new welcome', exact: true }).click();
  await expect(child).toContainText('new welcome was queued');
  expect(service.writes).toHaveLength(2);
  expect(service.writes[1].body).toEqual(first.body);
  expect(service.writes[1].key).toBe(first.key);
  expect(service.queued()).toBe(1);
});

test('current delivery authority denial removes prior recipient details and offers no send', async ({
  page,
}) => {
  const service = await fixture(page);
  const { admin, child } = await open(page, 1440);
  service.deny();
  await child.getByRole('button', { name: 'Check email service', exact: true }).click();
  await expect(admin).toContainText('Your current account cannot manage communications.');
  await expect(admin).not.toContainText('Alex Rivera');
  await expect(admin).not.toContainText('Private provider exception');
  expect(service.writes).toHaveLength(0);
});

test('Spanish mobile review requires duplicate consent without submitting on cancel', async ({
  page,
}) => {
  const service = await fixture(page);
  await page.setViewportSize({ width: 390, height: 1100 });
  await page.route('**/bff/api/v1/profile', (route) =>
    route.fulfill({
      json: {
        subject: context.subject,
        display_name: 'Alex Rivera',
        locale: 'es-ES',
        time_zone: 'Europe/Madrid',
        response_language: 'es',
        avatar_url: null,
        avatar_version: null,
      },
    }),
  );
  await page.goto('/library');
  await page.getByRole('button', { name: 'Abrir navegación', exact: true }).click();
  await openAdministration(page, 'Configuración');
  await page
    .getByRole('combobox', { name: 'Sección de configuración', exact: true })
    .selectOption('communications');
  const admin = page.locator('ffk-communications-admin');
  await admin.getByRole('button', { name: 'Historial de envíos', exact: true }).click();
  await admin.getByRole('button', { name: 'Detalles', exact: true }).click();
  const child = admin.locator('ffk-delivery-recovery');
  await child.getByRole('button', { name: 'Enviar una nueva bienvenida', exact: true }).click();
  const review = child.getByRole('region', { name: 'Revisar acción de entrega', exact: true });
  await expect(
    review.getByRole('button', { name: 'Preparar nueva bienvenida', exact: true }),
  ).toBeDisabled();
  await expect(review).toContainText('pueden llegar ambos mensajes');
  await review.getByRole('button', { name: 'Cancelar', exact: true }).click();
  await expect(review).toHaveCount(0);
  expect(service.writes).toHaveLength(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

for (const width of [1440, 390])
  test(`delivery observations update automatically and pause for review at ${width}px`, async ({
    page,
  }) => {
    await page.clock.install();
    const service = await fixture(page);
    service.status('queued');
    await page.setViewportSize({ width, height: 1000 });
    const { admin, child } = await open(page, width);
    service.status('delivered');
    await page.clock.fastForward(6000);
    await expect(admin.locator('tbody ffk-badge')).toHaveText('Delivered');
    expect(service.writes).toHaveLength(0);
    await child.getByRole('button', { name: 'Send a new welcome', exact: true }).click();
    const review = child.getByRole('region', { name: 'Review delivery action', exact: true });
    await expect(review).toBeVisible();
    const reads = service.reads();
    await page.clock.fastForward(65000);
    expect(service.reads()).toBe(reads);
    await expect(review).toBeVisible();
    await review.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(review).toHaveCount(0);
    await expect(
      child.getByRole('button', { name: 'Send a new welcome', exact: true }),
    ).toBeEnabled();
    service.readFailure(503);
    await page.clock.fastForward(31000);
    await expect(admin).toContainText('Communication status could not be updated');
    await expect(admin.locator('tbody ffk-badge')).toHaveText('Status not verified');
    await expect(
      child.getByRole('button', { name: 'Send a new welcome', exact: true }),
    ).toBeDisabled();
    await capture(page, `automatic-delivery-stale-${width}`);
    service.readFailure(0);
    await page.clock.fastForward(61000);
    await expect(admin.locator('tbody ffk-badge')).toHaveText('Delivered');
    expect(service.writes).toHaveLength(0);
    await capture(page, `automatic-delivery-current-${width}`);
  });

test('policy drafts survive focus and automatic observation deadlines', async ({ page }) => {
  await page.clock.install();
  const service = await fixture(page);
  const { admin } = await open(page, 1440);
  await admin.getByRole('button', { name: 'Policies', exact: true }).click();
  const language = admin.getByRole('combobox', {
    name: 'Default notification language',
    exact: false,
  });
  await language.selectOption('es-ES');
  const reads = service.reads();
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await page.clock.fastForward(65000);
  await expect(language).toHaveValue('es-ES');
  expect(service.reads()).toBe(reads);
  expect(service.writes).toHaveLength(0);
});
