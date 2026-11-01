// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { test, expect, type Page } from '@playwright/test';
import type { OrganizationPerson, OrganizationUnit } from '@fireflyframework/koinon-sdk';
import { openAdministration,  mockService } from './fixtures';

async function directoryService(page: Page) {
  await mockService(page);
  const department: OrganizationUnit = {
    id: 'engineering',
    tenant_id: 'tenant-one',
    name: 'Engineering',
    kind: 'department',
    revision: 1,
    has_children: true,
  };
  const team: OrganizationUnit = {
    id: 'platform',
    tenant_id: 'tenant-one',
    name: 'Knowledge platform',
    kind: 'team',
    parent_id: 'engineering',
    revision: 1,
    has_children: false,
  };
  const people: OrganizationPerson[] = [
    {
      id: 'alex',
      profile_id: 'profile-alex',
      display_name: 'Alex Rivera',
      job_title: 'Knowledge Operations Lead',
      unit: team,
      department,
      manager: { id: 'sam', display_name: 'Sam Taylor' },
      revision: 3,
      source: 'manual',
    },
    {
      id: 'sam',
      profile_id: 'profile-sam',
      display_name: 'Sam Taylor',
      job_title: 'Director of Engineering',
      unit: department,
      department,
      revision: 1,
      source: 'provider',
      provider_name: 'Corporate sign-in',
      managed_fields: ['job_title'],
      observation_status: 'current',
    },
    { id: null, profile_id: null, display_name: '', revision: 0, source: 'unassigned' },
  ];
  const writes: unknown[] = [];
  const reads: URL[] = [];
  const paged = (items: unknown[], url: URL) => ({
    items,
    total: items.length,
    page: Number(url.searchParams.get('page') ?? 1),
    page_size: 25,
    pages: items.length ? 1 : 0,
  });
  await page.route('**/bff/api/v1/tenants/*/organization/**', async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname;
    const json = (value: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
    if (request.method() === 'GET') reads.push(url);
    if (path.endsWith('/directory-settings'))
      return json({ tenant_id: 'tenant-one', visibility: 'administrators', revision: 1 });
    if (path.endsWith('/people/me')) return json(people[0]);
    if (path.endsWith('/units'))
      return json(
        paged(url.searchParams.get('parent_id') === 'engineering' ? [team] : [department], url),
      );
    if (path.endsWith('/reports')) return json(paged([people[0]], url));
    if (path.endsWith('/people')) {
      const q = (url.searchParams.get('q') ?? '').toLowerCase();
      return json(
        paged(
          people.filter((person) => person.display_name.toLowerCase().includes(q)),
          url,
        ),
      );
    }
    if (path.endsWith('/people/alex') && request.method() === 'PATCH') {
      expect(request.headers()['x-xsrf-token']).toBe('synthetic-csrf+token');
      const body = request.postDataJSON();
      writes.push(body);
      expect(body.expected_revision).toBe(3);
      people[0] = { ...people[0], job_title: body.job_title, revision: 4 };
      return json(people[0]);
    }
    if (path.endsWith('/people/alex')) return json(people[0]);
    return route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Synthetic directory route is not configured' }),
    });
  });
  return { people, writes, reads };
}

async function openPeople(page: Page, width: number) {
  await page.goto('/library');
  if (width < 700) await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  await openAdministration(page, 'Settings');
  if (width < 700)
    await page.getByLabel('Settings section', { exact: true }).selectOption('people');
  else await page.getByRole('button', { name: 'People', exact: true }).click();
  await expect(
    page
      .locator('ffk-organization-directory')
      .getByRole('heading', { name: 'People', exact: true }),
  ).toBeVisible();
}

for (const width of [1440, 390])
  test(`organization positions and hierarchy stay usable at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const service = await directoryService(page);
    await openPeople(page, width);
    const panel = page.locator('ffk-organization-directory');
    await expect(panel.getByText('Knowledge Operations Lead', { exact: true })).toBeVisible();
    await expect(panel.getByText('Name unavailable', { exact: true })).toBeVisible();
    const unknown = panel.getByRole('row').filter({ hasText: 'Name unavailable' });
    await expect(unknown.getByRole('button')).toBeDisabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    const dir = resolve(
      process.env['KOINON_DIRECTORY_CAPTURES'] ??
        '../../control/frontend-captures/organization-directory',
    );
    await mkdir(dir, { recursive: true });
    await page.evaluate(() => {
      document
        .querySelector<HTMLElement>('ffk-workbench')
        ?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 22px)');
      const note = document.createElement('div');
      note.textContent = 'Interface preview using controlled service data.';
      note.style.cssText =
        'position:fixed;bottom:0;inset-inline:0;z-index:99999;padding:5px;background:#855414;color:white;text-align:center;font:10px Manrope,sans-serif';
      document.body.append(note);
    });
    await page.screenshot({ path: resolve(dir, `people-${width}.png`), fullPage: true });
    const alex = panel.getByRole('row').filter({ hasText: 'Alex Rivera' });
    await alex.getByRole('button', { name: 'Edit position', exact: true }).click();
    const editor = panel.getByRole('region', { name: 'Organization information', exact: true });
    await editor
      .getByRole('textbox', { name: 'Job title', exact: true })
      .fill('Knowledge Platform Lead');
    await editor
      .getByRole('button', { name: 'Save organization information', exact: true })
      .click();
    await expect(panel.getByText('Knowledge Platform Lead', { exact: true })).toBeVisible();
    expect(service.writes).toHaveLength(1);
    const written = service.writes[0] as Record<string, unknown>;
    expect(written).not.toHaveProperty('roles');
    if (width < 700)
      await page.getByLabel('Settings section', { exact: true }).selectOption('structure');
    else await page.getByRole('button', { name: 'Organization structure', exact: true }).click();
    const structure = page.locator('ffk-organization-structure');
    await expect(structure.getByText('Engineering', { exact: true })).toBeVisible();
    await page.screenshot({ path: resolve(dir, `structure-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
  });
