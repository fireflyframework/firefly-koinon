// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService, context, setDarkAppearance } from './fixtures';
async function fixture(page: Page, spanish = false) {
  await mockService(page);
  const reads: URLSearchParams[] = [];
  const events = Array.from({ length: 67 }, (_, index) => ({
    id: 'audit-' + index,
    subject: 'https://synthetic-issuer.test|person-' + index,
    action: index % 2 ? 'catalog.created' : 'membership.created',
    resource_id: 'synthetic-resource-' + index,
    details: { role: 'editor' },
    created_at: `2026-10-${String((index % 27) + 1).padStart(2, '0')}T12:30:00Z`,
  }));
  const name = (subject: string) =>
    'Research colleague ' + subject.split('-').at(-1)!.padStart(2, '0');
  let denied = false;
  await page.route('**/bff/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (spanish && url.pathname.endsWith('/profile'))
      return json({
        subject: context.subject,
        display_name: 'Alex Rivera',
        locale: 'es-ES',
        time_zone: 'Europe/Madrid',
        response_language: 'es',
        avatar_url: null,
        avatar_version: null,
      });
    if (!url.pathname.endsWith('/audit')) return route.fallback();
    reads.push(url.searchParams);
    if (denied)
      return json(
        { code: 'ACCESS_DENIED', message: 'Audit read denied by current organization policy.' },
        403,
      );
    const q = url.searchParams.get('q')?.toLowerCase() ?? '',
      action = url.searchParams.get('action'),
      subject = url.searchParams.get('subject'),
      from = url.searchParams.get('from_date'),
      through = url.searchParams.get('through_date');
    const found = events.filter(
      (event) =>
        (!q || name(event.subject).toLowerCase().includes(q) || event.action.includes(q)) &&
        (!action || event.action === action) &&
        (!subject || event.subject === subject) &&
        (!from || event.created_at.slice(0, 10) >= from) &&
        (!through || event.created_at.slice(0, 10) <= through),
    );
    const sort = url.searchParams.get('sort') === 'action' ? 'action' : 'created_at',
      direction = url.searchParams.get('order') === 'asc' ? 1 : -1;
    found.sort((a, b) => a[sort].localeCompare(b[sort]) * direction || a.id.localeCompare(b.id));
    const current = Number(url.searchParams.get('page') || 1),
      size = Number(url.searchParams.get('page_size') || 25),
      items = found.slice((current - 1) * size, current * size);
    return json({
      items,
      actors: Object.fromEntries(
        items.map((event) => [
          event.subject,
          {
            subject: event.subject,
            display_name: name(event.subject),
            avatar_data_url: null,
            avatar_version: null,
          },
        ]),
      ),
      total: found.length,
      page: current,
      page_size: size,
      pages: Math.ceil(found.length / size),
    });
  });
  return { reads, setDenied: (value: boolean) => (denied = value) };
}
async function open(page: Page, spanish = false, mobile = false) {
  await page.goto('/');
  if (mobile)
    await page
      .getByRole('button', { name: spanish ? 'Abrir navegación' : 'Open navigation', exact: true })
      .click();
  await page
    .getByRole('button', { name: spanish ? 'Configuración' : 'Settings', exact: true })
    .click();
  if (mobile)
    await page
      .getByLabel(spanish ? 'Sección de configuración' : 'Settings section')
      .selectOption('audit');
  else await page.getByRole('button', { name: 'Audit', exact: true }).click();
  return page.locator('ffk-audit-panel');
}
test('audit sends server pages and date/action/person filters with human names', async ({
  page,
}) => {
  const service = await fixture(page);
  const panel = await open(page);
  await expect(panel.getByText('1–25 of 67 items')).toBeVisible();
  await panel.getByRole('button', { name: 'Next audit activity page' }).click();
  await expect(panel.getByText('26–50 of 67 items')).toBeVisible();
  expect(service.reads.at(-1)?.get('page')).toBe('2');
  await panel.getByRole('button', { name: 'More filters', exact: true }).click();
  const beforeDraft = service.reads.length;
  await panel.getByLabel('Action', { exact: true }).selectOption('membership.created');
  await panel.getByLabel('From date', { exact: true }).fill('2026-10-10');
  await panel.getByLabel('Through date', { exact: true }).fill('2026-10-12');
  expect(service.reads.length).toBe(beforeDraft);
  await expect(panel.getByRole('status')).toContainText('Filters changed');
  await panel.getByRole('button', { name: 'Apply filters', exact: true }).click();
  await expect.poll(() => service.reads.at(-1)?.get('from_date')).toBe('2026-10-10');
  expect(service.reads.at(-1)?.get('page')).toBe('1');
  expect(service.reads.at(-1)?.get('time_zone')).toBe('UTC');
  await expect(panel.locator('.filter-chip')).toHaveCount(2);
  await panel.getByRole('button', { name: /Remove filter · Date range/ }).click();
  await expect.poll(() => service.reads.at(-1)?.get('from_date')).toBe(null);
  expect(service.reads.at(-1)?.get('action')).toBe('membership.created');
  await panel.getByRole('button', { name: 'Clear filters', exact: true }).first().click();
  await panel
    .getByRole('searchbox', { name: 'Search audit activity' })
    .fill('Research colleague 02');
  await panel.getByRole('searchbox', { name: 'Search audit activity' }).press('Enter');
  await expect(panel.getByText('1–1 of 1 item')).toBeVisible();
  await panel.getByRole('button', { name: 'Filter by person · Research colleague 02' }).click();
  await expect
    .poll(() => service.reads.at(-1)?.get('subject'))
    .toBe('https://synthetic-issuer.test|person-2');
  await expect(panel).not.toContainText('synthetic-issuer');
  const trigger = panel.getByRole('button', { name: /View details/ }).first();
  const beforeDetails = service.reads.length;
  await trigger.click();
  const dialog = panel.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Research colleague 02', { exact: true })).toBeVisible();
  await dialog.getByText('Technical details', { exact: true }).click();
  await expect(dialog.locator('code').filter({ hasText: '2026-10-03T12:30:00Z' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
  expect(service.reads.length).toBe(beforeDetails);
});
for (const variant of [
  { width: 1440, height: 1000, spanish: false },
  { width: 390, height: 844, spanish: true },
])
  test(`audit layout ${variant.width}`, async ({ page }) => {
    await page.setViewportSize(variant);
    await fixture(page, variant.spanish);
    const panel = await open(page, variant.spanish, variant.width < 700);
    await expect(panel.locator('tbody tr')).toHaveCount(25);
    const directory = resolve('../../control/frontend-captures/audit');
    await mkdir(directory, { recursive: true });
    await page.evaluate(() => {
      (document.querySelector('ffk-workbench') as HTMLElement)?.style.setProperty(
        '--koinon-workspace-height',
        'calc(100dvh - 22px)',
      );
      const strip = document.createElement('div');
      strip.textContent = 'Controlled API fixtures · Interface review only';
      strip.style.cssText =
        'position:fixed;bottom:0;left:0;right:0;height:22px;background:#10110f;color:#f3f1eb;text-align:center;font:10px/22px sans-serif;z-index:99999';
      document.body.append(strip);
    });
    await page.screenshot({
      path: resolve(directory, `audit-default-${variant.width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    await panel
      .getByRole('button', { name: variant.spanish ? 'Más filtros' : 'More filters', exact: true })
      .click();
    if (variant.spanish) await setDarkAppearance(page, true);
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
      .toBe(variant.width);
    await expect(panel.locator('tbody tr').first()).not.toContainText('synthetic-issuer');
    await page.evaluate(() => {
      (document.querySelector('ffk-workbench') as HTMLElement)?.style.setProperty(
        '--koinon-workspace-height',
        'calc(100dvh - 22px)',
      );
      const strip = document.createElement('div');
      strip.textContent = 'Controlled API fixtures · Interface review only';
      strip.style.cssText =
        'position:fixed;bottom:0;left:0;right:0;height:22px;background:#10110f;color:#f3f1eb;text-align:center;font:10px/22px sans-serif;z-index:99999';
      document.body.append(strip);
    });
    await page.screenshot({
      path: resolve(directory, `audit-${variant.width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    const trigger = panel
      .getByRole('button', { name: variant.spanish ? /Ver detalles/ : /View details/ })
      .first();
    await trigger.click();
    const dialog = panel.getByRole('dialog');
    await expect(dialog).toBeVisible();
    const bounds = await dialog.boundingBox();
    expect(bounds!.width).toBeLessThanOrEqual(Math.min(480, variant.width) + 0.5);
    await expect(dialog.locator('pre')).not.toBeVisible();
    const close = await dialog.locator('button.close').boundingBox();
    expect(close!.height).toBeGreaterThanOrEqual(44);
    await dialog.evaluate((element) => {
      const note = document.createElement('div');
      note.textContent = 'Controlled API fixtures · Interface review only';
      note.style.cssText =
        'position:absolute;bottom:0;left:0;right:0;height:22px;background:#10110f;color:#f3f1eb;text-align:center;font:10px/22px sans-serif';
      element.append(note);
      (element as HTMLElement).style.paddingBottom = '22px';
    });
    await page.screenshot({
      path: resolve(directory, `audit-detail-${variant.width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    await expect(trigger).toBeFocused();
    await panel.locator('.results-heading').scrollIntoViewIfNeeded();
    await panel.locator('.results-heading').click();
    await page.screenshot({
      path: resolve(directory, `audit-list-${variant.width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
  });
test('audit denial is readable and retry reloads actual response', async ({ page }) => {
  const service = await fixture(page);
  service.setDenied(true);
  const panel = await open(page);
  await expect(panel.getByRole('alert')).toContainText('You do not have permission');
  service.setDenied(false);
  await panel.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(panel.getByText('1–25 of 67 items')).toBeVisible();
  await expect(panel.getByRole('alert')).toHaveCount(0);
});

test('audit reflows within a narrow embedded panel on a wide host', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await fixture(page);
  const panel = await open(page);
  await expect(panel.locator('tbody tr')).toHaveCount(25);
  await panel.evaluate((element) => ((element as HTMLElement).style.width = '360px'));
  await panel.getByRole('button', { name: 'More filters', exact: true }).click();
  await expect
    .poll(() =>
      panel.evaluate((element) => {
        const host = element.getBoundingClientRect();
        return Array.from(element.querySelectorAll('input,select,tbody tr')).every((node) => {
          const box = node.getBoundingClientRect();
          return box.left >= host.left - 1 && box.right <= host.right + 1;
        });
      }),
    )
    .toBe(true);
});
