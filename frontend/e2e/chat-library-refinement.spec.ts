// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { context, mockService } from './fixtures';

test.use({ hasTouch: true });

async function refinementService(page: Page) {
  const service = await mockService(page);
  for (const suffix of ['agents**', 'chat/threads**']) {
    await page.route('**/bff/api/v1/tenants/*/' + suffix, (route) =>
      route.fulfill({ json: { items: [], page: 1, page_size: 25, total: 0, pages: 0 } }),
    );
  }
  return service;
}

async function capture(page: Page, info: TestInfo, name: string) {
  if (process.env['KOINON_CAPTURE_REFINEMENT'] !== '1') return;
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: info.outputPath(name + '.png'),
    fullPage: true,
    animations: 'disabled',
  });
}

async function openNavigation(page: Page, name: 'Chat' | 'Library') {
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  await expect(page.getByRole('heading', { name: /Chat|Library/ }).first()).toBeAttached();
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('button', { name, exact: true }).click();
}

for (const width of [1440, 390]) {
  test(`chat controls reserve their own space in both panel states at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 1000 });
    await refinementService(page);
    await page.goto('/library');
    await openNavigation(page, 'Chat');
    await expect(page.locator('.conversation-title')).toBeVisible();
    const hide = page.getByRole('button', { name: 'Hide conversations', exact: true });
    if (await hide.isVisible()) await hide.click();
    const show = page.getByRole('button', { name: 'Show conversations', exact: true });
    await expect(show).toBeVisible();
    const control = (await show.boundingBox())!;
    const heading = (await page.locator('.conversation-title').boundingBox())!;
    expect(control.width).toBeGreaterThanOrEqual(44);
    expect(control.height).toBeGreaterThanOrEqual(44);
    expect(control.x + control.width <= heading.x || control.y + control.height <= heading.y).toBe(
      true,
    );
    await capture(page, info, `chat-collapsed-${width}`);
    await show.click();
    await expect(page.locator('.conversation-list')).toBeVisible();
    await capture(page, info, `chat-expanded-${width}`);
    if (width === 390) {
      await page.keyboard.press('Escape');
      await expect(show).toBeFocused();
    } else {
      const toggle = (await hide.boundingBox())!;
      const title = (await page.locator('.conversation-title').boundingBox())!;
      expect(toggle.x + toggle.width).toBeLessThanOrEqual(title.x);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });

  test(`empty Library exposes real space, project and folder creation at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 1000 });
    const service = await refinementService(page);
    service.rows.splice(0);
    await page.route('**/bff/api/v1/context', (route) =>
      route.fulfill({ json: { ...context, workspaces: [] } }),
    );
    await page.goto('/library');
    await expect(page.getByRole('button', { name: 'Create a space', exact: true })).toBeVisible();
    await capture(page, info, `library-empty-${width}`);
    const created: { kind: string; name: string }[] = [
      { kind: 'workspace', name: 'Team knowledge' },
      { kind: 'project', name: 'Customer research' },
      { kind: 'collection', name: 'Policy evidence' },
    ];
    for (const [index, item] of created.entries()) {
      const label = ['Create a space', 'Create a project', 'Create a folder'][index];
      await page.getByRole('button', { name: label, exact: true }).click();
      const dialog = page.getByRole('dialog', { name: label, exact: true });
      await expect(dialog).toBeVisible();
      await dialog.getByRole('textbox', { name: 'Name', exact: true }).fill(item.name);
      if (item.kind === 'collection') await capture(page, info, `library-create-folder-${width}`);
      await dialog
        .getByRole('button', { name: label.replace('Create a ', 'Create '), exact: true })
        .click();
      await expect(dialog).not.toBeVisible();
      const write = service.writes
        .filter((row) => row.method === 'POST' && row.path.endsWith('/catalog'))
        .at(-1)!;
      expect(write.body).toMatchObject({
        kind: item.kind,
        name: item.name,
        parent_id: index === 0 ? null : service.rows[index - 1].id,
      });
      if (item.kind !== 'collection')
        await test.step('Open created ' + item.kind, async () => {
          const details = page.getByRole('button', { name: 'Close details', exact: true });
          await expect(details).toBeVisible();
          await details.click();
          await expect(page.getByLabel('Resource details', { exact: true })).toHaveCount(0);
          await page.getByRole('button', { name: item.name, exact: true }).click();
          await expect(page.getByRole('heading', { name: item.name, exact: true })).toBeVisible();
        });
    }
    expect(
      service.writes.filter((row) => row.method === 'POST' && row.path.endsWith('/catalog')),
    ).toHaveLength(3);
    await expect(page.getByRole('button', { name: 'Add knowledge', exact: true })).toBeVisible();
  });
}

for (const width of [1440, 390]) {
  test(`Chat is the default and administrator pages live in the account menu at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 1000 });
    await refinementService(page);
    await page.goto('/');
    await expect(page.locator('.conversation-title')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Library', exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Account menu', exact: true }).click();
    const menu = page.getByRole('menu', { name: 'Account menu', exact: true });
    await expect(menu.getByRole('menuitem', { name: 'Settings', exact: true })).toBeVisible();
    await expect(menu.getByRole('menuitem', { name: 'Activity', exact: true })).toBeVisible();
    await capture(page, info, `avatar-admin-${width}`);
    await menu.getByRole('menuitem', { name: 'Sign out', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Sign out?', exact: true });
    await expect(dialog).toBeVisible();
    let posts = 0;
    await page.route('**/logout', (route) => {
      ++posts;
      return route.fulfill({ status: 204 });
    });
    await capture(page, info, `logout-confirm-${width}`);
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(dialog).not.toBeVisible();
    expect(posts).toBe(0);
    await expect(page.locator('.conversation-title')).toBeVisible();
  });
  test(`reader cannot open administrator pages from menu or direct links at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 1000 });
    await refinementService(page);
    const reader = {
      ...context,
      tenants: [
        { ...context.tenants[0], roles: ['viewer'], permissions: ['catalog:read', 'chat:use'] },
      ],
      memberships: [],
    };
    await page.route('**/bff/api/v1/context', (route) => route.fulfill({ json: reader }));
    const adminReads: string[] = [];
    page.on('request', (request) => {
      if (
        /\/jobs(?:\?|$)|\/activity\/(?:administration|personal)|\/providers(?:\?|$)/.test(
          request.url(),
        )
      )
        adminReads.push(request.url());
    });
    for (const path of ['/settings', '/activity']) {
      await page.goto(path);
      await expect(page.locator('.conversation-title')).toBeVisible();
      await expect(page).toHaveURL(/\/$/);
    }
    await page.getByRole('button', { name: 'Account menu', exact: true }).click();
    const menu = page.getByRole('menu', { name: 'Account menu', exact: true });
    await expect(menu.getByRole('menuitem', { name: 'Settings', exact: true })).toHaveCount(0);
    await expect(menu.getByRole('menuitem', { name: 'Activity', exact: true })).toHaveCount(0);
    await expect(menu.getByRole('menuitem', { name: 'Your account', exact: true })).toBeVisible();
    await capture(page, info, `avatar-reader-${width}`);
    expect(adminReads).toEqual([]);
    await page.keyboard.press('Escape');
    await page.goto('/library');
    await expect(page.getByRole('button', { name: 'Create a space', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Add knowledge', exact: true })).toHaveCount(0);
  });
}

test('confirmed native-style redirect logout succeeds after the server clears the session', async ({
  page,
}) => {
  await refinementService(page);
  let signedOut = false;
  const posts: string[] = [];
  await page.route('**/bff/api/v1/context', async (route) =>
    signedOut
      ? route.fulfill({ status: 401, json: { code: 'UNAUTHENTICATED' } })
      : route.fallback(),
  );
  await page.route('**/logout', (route) => {
    posts.push(route.request().method());
    signedOut = true;
    return route.fulfill({ status: 302, headers: { location: '/login?logout' } });
  });
  await page.route('**/login?logout', (route) => route.fulfill({ status: 404, body: 'Not found' }));
  await page.route('**/auth/me', (route) =>
    signedOut ? route.fulfill({ status: 401, json: { detail: 'Sign in required' } }) : route.fallback(),
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Sign out?', exact: true })).toBeVisible();
  expect(posts).toEqual([]);
  await page.getByRole('dialog').getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Welcome to koinon', exact: true })).toBeVisible();
  expect(posts).toEqual(['POST']);
  await expect(page.getByRole('alert')).toHaveCount(0);
});

for (const width of [1440, 390]) {
  test(`protected roots and nested Library folder moves use fresh server state at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const service = await refinementService(page);
    service.rows[0].system_managed = true;
    const source = service.rows.find((row) => row.id === 'collection-one')!;
    source.updated_at = '2026-11-01T01:00:00Z';
    const destination = { ...source, id: 'reviewed-folder', name: 'Reviewed evidence' };
    service.rows.push(destination);
    const observedAt = '2026-11-01T02:00:00Z';
    await page.route('**/bff/api/v1/tenants/tenant-one/catalog/collection-one', (route) =>
      route.fulfill({ json: { ...source, updated_at: observedAt } }),
    );
    const moves: unknown[] = [];
    await page.route('**/bff/api/v1/tenants/tenant-one/catalog/collection-one/move', (route) => {
      const body = route.request().postDataJSON();
      moves.push(body);
      source.parent_id = body.parent_id;
      source.updated_at = '2026-11-01T03:00:00Z';
      return route.fulfill({ json: source });
    });
    await page.goto('/library');
    await page
      .getByRole('button', { name: 'Details for Research operations', exact: true })
      .click();
    const inspector = page.locator('ffk-inspector');
    await expect(inspector.getByText('System space', { exact: true })).toBeVisible();
    await expect(inspector.getByRole('button', { name: 'Archive', exact: true })).toHaveCount(0);
    await expect(
      inspector.getByRole('button', { name: 'Move Library folder', exact: true }),
    ).toHaveCount(0);
    await inspector.getByRole('button', { name: 'Close details', exact: true }).click();
    await page.getByRole('button', { name: 'Research operations', exact: true }).click();
    await page.getByRole('button', { name: 'Operations intelligence', exact: true }).click();
    await page.getByRole('button', { name: 'Details for Reference library', exact: true }).click();
    await inspector.getByRole('button', { name: 'Move Library folder', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Move Library folder', exact: true });
    await expect(dialog).toBeVisible();
    await expect(
      dialog.getByRole('treeitem', { name: 'Reference library', exact: true }),
    ).toHaveAttribute('aria-disabled', 'true');
    await dialog.getByRole('treeitem', { name: 'Reviewed evidence', exact: true }).click();
    await dialog.getByRole('button', { name: 'Move Library folder', exact: true }).click();
    await expect(dialog).not.toBeVisible();
    expect(moves).toEqual([
      {
        parent_id: 'reviewed-folder',
        expected_parent_id: 'project-one',
        expected_updated_at: observedAt,
      },
    ]);
    expect(source.parent_id).toBe('reviewed-folder');
    await inspector.getByRole('button', { name: 'Close details', exact: true }).click();
    await page.getByRole('button', { name: 'Reviewed evidence', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Create a folder', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add knowledge', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Create a folder', exact: true }).click();
    const create = page.getByRole('dialog', { name: 'Create a folder', exact: true });
    await create.getByRole('textbox', { name: 'Name', exact: true }).fill('Nested review');
    await create.getByRole('button', { name: 'Create folder', exact: true }).click();
    await expect(create).not.toBeVisible();
    expect(
      service.writes.filter((row) => row.method === 'POST' && row.path.endsWith('/catalog')).at(-1)
        ?.body,
    ).toMatchObject({ kind: 'collection', parent_id: 'reviewed-folder', name: 'Nested review' });
  });
}
