// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { Membership, Invitation } from '@fireflyframework/koinon-sdk';
import { mockService, context as baseContext, setDarkAppearance } from './fixtures';
async function fixture(page: Page, spanish = false) {
  await mockService(page);
  const members: Membership[] = Array.from({ length: 56 }, (_, index) => ({
    id: 'member-' + index,
    subject: 'https://private-issuer.test|person-' + index,
    tenant_id: 'tenant-one',
    workspace_id: index % 2 ? 'workspace-one' : null,
    role: index === 0 ? 'admin' : index % 3 ? 'viewer' : 'editor',
    active: true,
  }));
  const invitations: Invitation[] = [];
  const reads: URLSearchParams[] = [];
  const writes: { method: string; path: string; body: unknown; csrf: string | undefined }[] = [];
  const name = (subject: string) =>
    subject === members[0]?.subject
      ? 'Alex Rivera'
      : 'Researcher ' + subject.split('-').at(-1)?.padStart(2, '0');
  await page.route('**/bff/api/v1/**', async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (path.endsWith('/context'))
      return json({
        ...baseContext,
        memberships: [{ ...members[0], subject: baseContext.subject }],
      });
    if (spanish && path.endsWith('/profile'))
      return json({
        subject: baseContext.subject,
        display_name: 'Alex Rivera',
        locale: 'es-ES',
        time_zone: 'Europe/Madrid',
        response_language: 'es',
        avatar_url: null,
        avatar_version: null,
      });
    if (!path.includes('/members') && !path.includes('/people') && !path.includes('/invitations'))
      return route.fallback();
    if (request.method() !== 'GET')
      writes.push({
        method: request.method(),
        path,
        body: request.postData() ? request.postDataJSON() : null,
        csrf: request.headers()['x-xsrf-token'],
      });
    if (path.endsWith('/people')) {
      const q = url.searchParams.get('q')?.toLowerCase() ?? '';
      const found = members.filter((member) => name(member.subject).toLowerCase().includes(q));
      const start = Number(url.searchParams.get('after') || 0),
        items = found.slice(start, start + 20).map((member) => ({
          subject: member.subject,
          display_name: name(member.subject),
          profile_id: null,
          avatar_version: null,
          avatar_url: null,
        }));
      return json({ items, next_cursor: found.length > start + 20 ? String(start + 20) : null });
    }
    if (path.endsWith('/members')) {
      if (request.method() === 'GET') {
        reads.push(url.searchParams);
        const scope = url.searchParams.get('scope'),
          workspace = url.searchParams.get('workspace_id'),
          role = url.searchParams.get('role'),
          q = url.searchParams.get('q')?.toLowerCase() ?? '';
        const found = members.filter(
          (member) =>
            member.active &&
            (!workspace || member.workspace_id === workspace) &&
            (scope !== 'tenant' || !member.workspace_id) &&
            (!role || member.role === role) &&
            name(member.subject).toLowerCase().includes(q),
        );
        const current = Number(url.searchParams.get('page') || 1),
          size = Number(url.searchParams.get('page_size') || 25),
          items = found.slice((current - 1) * size, current * size);
        return json({
          items,
          actors: Object.fromEntries(
            items.map((member) => [
              member.subject,
              {
                subject: member.subject,
                display_name: name(member.subject),
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
      }
      const body = request.postDataJSON(),
        row = { id: 'added', tenant_id: 'tenant-one', active: true, ...body };
      if (
        members.some(
          (member) =>
            member.subject === body.subject &&
            member.workspace_id === body.workspace_id &&
            member.active,
        )
      )
        return json({ code: 'MEMBERSHIP_EXISTS', detail: 'Membership already exists' }, 409);
      members.push(row);
      return json(row, 201);
    }
    if (/\/members\//.test(path)) {
      const member = members.find((row) => row.id === path.split('/').at(-1))!;
      if (member.id === 'member-0')
        return json(
          { code: 'LAST_ADMIN', detail: 'Tenant must retain an active administrator' },
          409,
        );
      if (request.method() === 'DELETE') {
        member.active = false;
        return route.fulfill({ status: 204 });
      }
      Object.assign(member, request.postDataJSON());
      return json(member);
    }
    if (path.endsWith('/invitations')) {
      if (request.method() === 'POST') {
        const row: Invitation = {
          ...request.postDataJSON(),
          id: 'invitation-' + invitations.length,
          tenant_id: 'tenant-one',
          workspace_id: request.postDataJSON().workspace_id ?? null,
          created_by: baseContext.subject,
          created_at: '2026-10-27T12:00:00Z',
          expires_at: '2026-11-03T12:00:00Z',
          status: 'pending',
        };
        invitations.push(row);
        return json(
          { invitation: row, token: 'synthetic-invitation-secret-for-ui-verification-only' },
          201,
        );
      }
      const items = invitations.filter(
        (row) => row.status === (url.searchParams.get('status') || 'pending'),
      );
      return json({
        items,
        total: items.length,
        page: 1,
        page_size: 25,
        pages: items.length ? 1 : 0,
      });
    }
    if (request.method() === 'DELETE' && path.includes('/invitations/')) {
      invitations.find((row) => row.id === path.split('/').at(-1))!.status = 'revoked';
      return route.fulfill({ status: 204 });
    }
    return route.fallback();
  });
  return { members, invitations, reads, writes };
}
async function open(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'People & access', exact: true }).click();
  await expect(page.locator('ffk-people-access h2')).toHaveText('People & access');
}

test('named membership list uses actual server pages and filters', async ({ page }) => {
  const service = await fixture(page);
  await open(page);
  const panel = page.locator('ffk-people-access');
  await expect(panel.getByText('1–25 of 56 items')).toBeVisible();
  await panel.getByRole('button', { name: 'Next role assignments page' }).click();
  await expect(panel.getByText('26–50 of 56 items')).toBeVisible();
  expect(service.reads.at(-1)?.get('page')).toBe('2');
  await panel.getByRole('combobox', { name: 'Role', exact: true }).selectOption('editor');
  await expect(panel.getByText('1–18 of 18 items')).toBeVisible();
  expect(service.reads.at(-1)?.get('role')).toBe('editor');
  await panel.getByRole('searchbox', { name: 'Search role assignments' }).fill('Researcher 03');
  await panel.getByRole('searchbox', { name: 'Search role assignments' }).press('Enter');
  await expect(panel.getByText('1–1 of 1 item')).toBeVisible();
  await expect(panel.getByText('Researcher 03', { exact: true })).toBeVisible();
  await expect(panel).not.toContainText('private-issuer');
});

test('existing person selection grants a scoped role, edits it, and confirms removal', async ({
  page,
}) => {
  const service = await fixture(page);
  await open(page);
  const panel = page.locator('ffk-people-access');
  await panel.getByRole('button', { name: 'Add existing person', exact: true }).click();
  await panel.getByRole('searchbox', { name: 'Search people' }).fill('Researcher 02');
  await panel.getByRole('button', { name: 'Search', exact: true }).click();
  await panel.getByRole('button', { name: 'Researcher 02 Select' }).click();
  await panel
    .getByRole('combobox', { name: 'Access scope', exact: true })
    .selectOption('workspace-one');
  await panel.getByRole('combobox', { name: 'Role', exact: true }).selectOption('analyst');
  await panel.getByRole('button', { name: 'Save access' }).click();
  await expect(panel.getByText('Access saved.')).toBeVisible();
  expect(
    service.writes.find((write) => write.method === 'POST' && write.path.endsWith('/members'))
      ?.body,
  ).toEqual({
    subject: 'https://private-issuer.test|person-2',
    role: 'analyst',
    workspace_id: 'workspace-one',
  });
  expect(service.writes.at(-1)?.csrf).toBe('synthetic-csrf+token');
  await panel.getByRole('searchbox', { name: 'Search role assignments' }).fill('Researcher 02');
  await panel.getByRole('searchbox', { name: 'Search role assignments' }).press('Enter');
  const row = panel
    .getByRole('row')
    .filter({ has: page.getByText('Research operations', { exact: true }) });
  await row.getByRole('button', { name: 'Change access, Researcher 02' }).click();
  await expect(panel.getByRole('heading', { name: 'Change access', exact: true })).toBeVisible();
  await panel.getByRole('combobox', { name: 'Role', exact: true }).selectOption('editor');
  await panel.getByRole('button', { name: 'Save access' }).click();
  await expect(
    panel.getByRole('heading', { name: 'Change access', exact: true }),
  ).not.toBeVisible();
  await row.getByRole('button', { name: 'Remove role, Researcher 02' }).click();
  await panel.getByRole('button', { name: 'Remove role', exact: true }).click();
  await expect(panel.getByText('Access removed.')).toBeVisible();
});

test('last administrator removal returns useful conflict and preserves row', async ({ page }) => {
  await fixture(page);
  await open(page);
  const panel = page.locator('ffk-people-access');
  await panel.getByRole('button', { name: 'Remove role, Alex Rivera' }).click();
  await panel.getByRole('button', { name: 'Remove role', exact: true }).click();
  await expect(
    panel.getByRole('alert').filter({ hasText: 'Keep at least one administrator' }),
  ).toBeVisible();
  await expect(panel.getByText('Alex Rivera', { exact: true }).first()).toBeVisible();
});

test('private invitation is shown once then can be revoked without exposing its secret in lists', async ({
  page,
}) => {
  const service = await fixture(page);
  await open(page);
  const panel = page.locator('ffk-people-access');
  await panel.getByRole('button', { name: 'Invite person', exact: true }).click();
  await panel.getByLabel('Invitation label (optional)').fill('Research onboarding');
  await panel.getByRole('combobox', { name: 'Role', exact: true }).selectOption('editor');
  await panel.getByRole('button', { name: 'Create invitation link' }).click();
  await expect(panel.getByLabel('Private invitation link')).toHaveValue(
    /#invite=synthetic-invitation-secret/,
  );
  await panel.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(panel).not.toContainText('synthetic-invitation-secret');
  await expect(panel.getByRole('cell').filter({ hasText: 'Research onboarding' })).toBeVisible();
  await panel.getByRole('button', { name: 'Revoke', exact: true }).click();
  await panel.getByRole('button', { name: 'Revoke link', exact: true }).click();
  await expect(panel.getByText('No invitations in this view.')).toBeVisible();
  expect(service.invitations[0].status).toBe('revoked');
});

for (const variant of [
  { width: 1440, height: 1000, dark: false, spanish: false },
  { width: 390, height: 844, dark: true, spanish: true },
])
  test(`people access visual ${variant.width} ${variant.spanish ? 'Spanish' : 'English'}`, async ({
    page,
  }) => {
    await page.setViewportSize(variant);
    await fixture(page, variant.spanish);
    await page.goto('/');
    if (variant.width < 700)
      await page
        .getByRole('button', {
          name: variant.spanish ? 'Abrir navegación' : 'Open navigation',
          exact: true,
        })
        .click();
    await page
      .getByRole('button', { name: variant.spanish ? 'Configuración' : 'Settings', exact: true })
      .click();
    if (variant.width < 700)
      await page
        .getByLabel(variant.spanish ? 'Sección de configuración' : 'Settings section')
        .selectOption('people');
    else await page.getByRole('button', { name: 'People & access', exact: true }).click();
    const panel = page.locator('ffk-people-access');
    await expect(panel.locator('tbody tr').first()).toBeVisible();
    const overflow = await page.evaluate(() => {
      const collect = (root: Document | ShadowRoot): Element[] =>
        Array.from(root.querySelectorAll('*')).flatMap((element) => [
          element,
          ...(element.shadowRoot ? collect(element.shadowRoot) : []),
        ]);
      return collect(document)
        .filter((element) => element.getBoundingClientRect().right > innerWidth + 1)
        .map((element) => ({
          tag: element.tagName,
          class: element.className,
          right: element.getBoundingClientRect().right,
          width: element.getBoundingClientRect().width,
          overflow: getComputedStyle(element).overflowX,
          parent: element.parentElement?.className,
        }))
        .slice(0, 60);
    });
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) {
      await writeFile(resolve('../../control/people-overflow.json'), JSON.stringify(overflow));
      await test.info().attach('overflow.json', {
        body: JSON.stringify(overflow),
        contentType: 'application/json',
      });
    }
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
      .toBe(variant.width);
    if (variant.dark) await setDarkAppearance(page, variant.spanish);
    await page.evaluate(() => {
      (document.querySelector('ffk-workbench') as HTMLElement)?.style.setProperty(
        '--koinon-workspace-height',
        'calc(100dvh - 22px)',
      );
      const strip = document.createElement('div');
      strip.textContent = 'Interface preview using controlled service data.';
      strip.style.cssText =
        'position:fixed;bottom:0;left:0;right:0;height:22px;background:#10110f;color:#f3f1eb;text-align:center;font:10px/22px sans-serif;z-index:99999';
      document.body.append(strip);
    });
    const directory = resolve('../../control/frontend-captures/people-access');
    await mkdir(directory, { recursive: true });
    await page.screenshot({
      path: resolve(directory, `people-${variant.width}.png`),
      fullPage: true,
    });
    if (variant.width < 700) {
      await page
        .getByRole('region', {
          name: variant.spanish ? 'Contenido de configuración' : 'Settings content',
          exact: true,
        })
        .evaluate((element) => {
          element.scrollTop = 360;
        });
      await page.screenshot({
        path: resolve(directory, `people-${variant.width}-list.png`),
        fullPage: true,
      });
      await page
        .getByRole('region', {
          name: variant.spanish ? 'Contenido de configuración' : 'Settings content',
          exact: true,
        })
        .evaluate((element) => {
          element.scrollTop = 0;
        });
    }
    await panel
      .getByRole('button', {
        name: variant.spanish ? 'Invitar persona' : 'Invite person',
        exact: true,
      })
      .click();
    await expect(panel.locator('h2')).toHaveText(
      variant.spanish ? 'Invitar a una persona' : 'Invite a person',
    );
    await page.screenshot({
      path: resolve(directory, `invite-${variant.width}.png`),
      fullPage: true,
    });
  });

test('keyboard entry and return restore focus and keep the narrow table inside its scroller', async ({
  page,
}) => {
  await fixture(page);
  await open(page);
  const panel = page.locator('ffk-people-access');
  const invite = panel.getByRole('button', { name: 'Invite person', exact: true });
  await invite.focus();
  await page.keyboard.press('Enter');
  await expect(panel.getByRole('heading', { name: 'Invite a person', exact: true })).toBeVisible();
  await panel.getByRole('button', { name: 'Back to people', exact: true }).click();
  await expect(invite).toBeFocused();
  await page.setViewportSize({ width: 780, height: 844 });
  const table = panel.getByRole('region', { name: 'Role assignments', exact: true });
  await table.evaluate((element) => {
    (element as HTMLElement).style.width = '440px';
  });
  await expect
    .poll(() => table.evaluate((element) => element.scrollWidth > element.clientWidth))
    .toBe(true);
  await table.focus();
  await page.keyboard.press('Tab');
  await expect(panel.getByRole('button', { name: 'Change access, Alex Rivera' })).toBeFocused();
  await expect.poll(() => table.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(780);
});

test('mobile role rows show the person, scope and actions together without horizontal scrolling', async ({
  page,
}) => {
  await fixture(page);
  await open(page);
  await page.setViewportSize({ width: 390, height: 844 });
  const panel = page.locator('ffk-people-access');
  const row = panel
    .getByRole('row')
    .filter({ has: page.getByText('Alex Rivera', { exact: true }) });
  await row.scrollIntoViewIfNeeded();
  await expect(row.getByText('Alex Rivera', { exact: true })).toBeInViewport();
  await expect(row.getByText('Entire organization', { exact: true })).toBeInViewport();
  await expect(row.getByRole('button', { name: 'Change access, Alex Rivera' })).toBeInViewport();
  await expect(row.getByRole('button', { name: 'Remove role, Alex Rivera' })).toBeInViewport();
  expect(
    await panel
      .getByRole('region', { name: 'Role assignments', exact: true })
      .evaluate((element) => element.scrollWidth <= element.clientWidth),
  ).toBe(true);
});
