// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import type { ChatFolder, ChatThread } from '@fireflyframework/koinon-sdk';
import { mockService } from './fixtures';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
async function groupedFixture(page: Page) {
  await mockService(page, { organizationAgent: 'agent-one' });
  const stamp = '2026-10-26T10:00:00Z';
  const folder = (id: string, name: string, parent_id: string | null = null): ChatFolder => ({
    id,
    name,
    parent_id,
    scope: { workspace_id: 'workspace-one', project_id: 'project-one' },
    revision: 1,
    conversation_count: 0,
    created_at: stamp,
    updated_at: stamp,
  });
  const folders = [
    folder('research', 'Research'),
    folder('nested', 'Nested notes', 'research'),
    ...Array.from({ length: 14 }, (_, i) =>
      folder('folder-' + i, 'Team ' + String(i + 1).padStart(2, '0')),
    ),
  ];
  const threads: ChatThread[] = Array.from({ length: 18 }, (_, i) => ({
    id: 'recent-' + i,
    title: 'Recent ' + String(i + 1).padStart(2, '0'),
    title_source: 'manual',
    revision: 1,
    folder_id: null,
    archived_at: null,
    scope: { workspace_id: 'workspace-one', project_id: 'project-one' },
    created_at: stamp,
    updated_at: `2026-10-26T${String(i + 1).padStart(2, '0')}:00:00Z`,
  }));
  threads.push({ ...threads[0], id: 'filed', title: 'Filed conversation', folder_id: 'research' });
  const calls: {
    method: string;
    path: string;
    query: URLSearchParams;
    body: Record<string, unknown>;
    csrf: string | undefined;
  }[] = [];
  let conflict = false;
  await page.route('**/bff/api/v1/tenants/*/**', async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname,
      method = request.method();
    const body =
      method === 'GET' || method === 'DELETE'
        ? {}
        : (request.postDataJSON() as Record<string, unknown>);
    calls.push({
      method,
      path,
      query: url.searchParams,
      body,
      csrf: request.headers()['x-xsrf-token'],
    });
    const json = (data: unknown, status = 200) =>
      route.fulfill(
        status === 204
          ? { status }
          : { status, contentType: 'application/json', body: JSON.stringify(data) },
      );
    const paging = <T>(items: T[]) => {
      const current = Number(url.searchParams.get('page') || 1),
        size = Number(url.searchParams.get('page_size') || 25);
      return {
        items: items.slice((current - 1) * size, current * size),
        total: items.length,
        page: current,
        page_size: size,
        pages: Math.ceil(items.length / size),
      };
    };
    if (path.endsWith('/agents'))
      return json({
        items: [
          {
            id: 'agent-one',
            name: 'Controlled local guide',
            description: 'Controlled browser fixture',
            provider_id: 'provider',
            model_id: 'fixture',
            tools: [],
            scope: {},
            instructions: '',
            enabled: true,
            configured: true,
            can_run: true,
            revision: 1,
            status: 'ready',
            checks: [],
          },
        ],
      });
    if (path.endsWith('/chat/folders')) {
      if (method === 'POST') {
        const parent = folders.find((row) => row.id === body['parent_id']);
        const row = folder('created-' + folders.length, String(body['name']), parent?.id ?? null);
        row.scope = parent?.scope ?? (body['scope'] as ChatFolder['scope']) ?? {};
        folders.push(row);
        return json(row, 201);
      }
      const items = folders
        .filter(
          (row) =>
            (url.searchParams.get('root_only') !== 'true' || row.parent_id === null) &&
            (!url.searchParams.get('parent_id') ||
              row.parent_id === url.searchParams.get('parent_id')) &&
            (!url.searchParams.get('workspace_id') ||
              row.scope.workspace_id === url.searchParams.get('workspace_id')) &&
            (!url.searchParams.get('q') ||
              row.name.toLowerCase().includes(url.searchParams.get('q')!.toLowerCase())),
        )
        .sort((a, b) => a.name.localeCompare(b.name));
      return json(
        paging(
          items.map((row) => ({
            ...row,
            conversation_count: threads.filter(
              (thread) => thread.folder_id === row.id && !thread.archived_at,
            ).length,
          })),
        ),
      );
    }
    const folderMatch = path.match(/\/chat\/folders\/([^/]+)$/);
    if (folderMatch) {
      const row = folders.find((value) => value.id === decodeURIComponent(folderMatch[1]));
      if (!row) return json({ code: 'UNAVAILABLE', detail: 'Folder unavailable' }, 404);
      if (method === 'PATCH' || method === 'DELETE') {
        const revision =
          method === 'DELETE'
            ? Number(url.searchParams.get('expected_revision'))
            : body['expected_revision'];
        if (revision !== row.revision)
          return json({ code: 'CONFLICT', detail: 'Folder changed' }, 409);
        if (method === 'DELETE') {
          for (const child of folders.filter((value) => value.parent_id === row.id)) {
            child.parent_id = row.parent_id;
            child.revision++;
          }
          for (const thread of threads.filter((value) => value.folder_id === row.id)) {
            thread.folder_id = null;
            thread.revision++;
            thread.updated_at = new Date().toISOString();
          }
          folders.splice(folders.indexOf(row), 1);
          return json(null, 204);
        }
        row.name = String(body['name']);
        row.revision++;
      }
      return json(row);
    }
    if (path.endsWith('/chat/threads')) {
      if (method === 'POST') {
        const parent = folders.find((row) => row.id === body['folder_id']);
        const row: ChatThread = {
          ...threads[0],
          id: 'new-' + threads.length,
          title: String(body['title'] || 'New conversation'),
          title_source: 'default',
          revision: 1,
          folder_id: parent?.id ?? null,
          scope: parent?.scope ?? (body['scope'] as ChatThread['scope']) ?? {},
        };
        threads.push(row);
        return json(row, 201);
      }
      const q = (url.searchParams.get('q') || '').toLowerCase(),
        status = url.searchParams.get('status') || 'active';
      const items = threads
        .filter(
          (row) =>
            (status === 'all' || (status === 'archived' ? !!row.archived_at : !row.archived_at)) &&
            (!q || row.title.toLowerCase().includes(q)) &&
            (url.searchParams.get('unfiled') !== 'true' || row.folder_id === null) &&
            (!url.searchParams.get('folder_id') ||
              row.folder_id === url.searchParams.get('folder_id')) &&
            (!url.searchParams.get('workspace_id') ||
              row.scope.workspace_id === url.searchParams.get('workspace_id')) &&
            (!url.searchParams.get('project_id') ||
              row.scope.project_id === url.searchParams.get('project_id')),
        )
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
      return json(paging(items));
    }
    if (path.endsWith('/attachments/capabilities'))
      return json({
        storage: { available: false, reason: 'Private files are outside this controlled fixture.' },
        database: { available: true, reason: 'Controlled fixture' },
        extraction: { available: null, reason: 'Not exercised' },
        limits: {
          max_file_bytes: 10485760,
          max_image_bytes: 5242880,
          max_selected: 5,
          max_thread_files: 20,
          max_thread_bytes: 104857600,
          max_model_text_chars: 50000,
          max_model_binary_bytes: 10485760,
          extraction_timeout_seconds: 60,
          ttl_seconds: 3600,
        },
        formats: [],
        promotion: {},
      });
    const threadMatch = path.match(/\/chat\/threads\/([^/]+)(?:\/(messages|title-suggestion))?$/);
    if (threadMatch) {
      const row = threads.find((value) => value.id === threadMatch[1]);
      if (!row) return json({ code: 'UNAVAILABLE', detail: 'Conversation unavailable' }, 404);
      if (threadMatch[2] === 'messages') return json({ items: [], next_cursor: null });
      if (threadMatch[2] === 'title-suggestion')
        return json({ title: 'Reviewed AI proposal', based_on_revision: row.revision });
      if (method === 'PATCH') {
        if (conflict) {
          conflict = false;
          row.revision++;
          row.title = 'Changed before save';
        }
        if (body['expected_revision'] !== row.revision)
          return json({ code: 'CONFLICT', detail: 'Conversation changed' }, 409);
        if ('title' in body) {
          row.title = String(body['title']);
          row.title_source = 'manual';
        }
        if ('folder_id' in body) row.folder_id = body['folder_id'] as string | null;
        if ('archived' in body)
          row.archived_at = body['archived'] ? new Date().toISOString() : null;
        row.revision++;
        row.updated_at = new Date().toISOString();
      }
      return json(row);
    }
    return route.fallback();
  });
  return {
    folders,
    threads,
    calls,
    conflictNext: () => {
      conflict = true;
    },
  };
}
async function openSidebar(page: Page, mobile = false) {
  await page.goto('/');
  const navigation = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await navigation.isVisible()) await navigation.click();
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  if (mobile) await page.getByRole('button', { name: 'Show conversations', exact: true }).click();
  const sidebar = page.locator('ffk-conversation-sidebar');
  await expect(
    sidebar.getByRole('button', { name: 'Conversation options', exact: true }),
  ).toBeVisible();
  await expect(sidebar.locator('.thread-name').first()).toBeVisible();
  await expect(page.locator('.chat-error')).toHaveCount(0);
  return sidebar;
}
async function capture(page: Page, name: string) {
  await page.evaluate(() => {
    const host = document.querySelector('ffk-workbench') as HTMLElement;
    host?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 22px)');
    if (document.querySelector('[data-group-proof]')) return;
    const strip = document.createElement('div');
    strip.dataset['groupProof'] = 'true';
    strip.textContent = 'Controlled API fixtures · Grouped sidebar review';
    strip.style.cssText =
      'position:fixed;bottom:0;left:0;right:0;height:22px;background:#10110f;color:#f3f1eb;text-align:center;font:10px/22px sans-serif;z-index:99999';
    document.body.append(strip);
  });
  const folder = resolve('../../control/frontend-captures/conversation-sidebar');
  await mkdir(folder, { recursive: true });
  await page.screenshot({ path: resolve(folder, name), fullPage: true, animations: 'disabled' });
}
test('grouped sidebar uses real pages and lazy folders without replacing the active chat', async ({
  page,
}) => {
  const api = await groupedFixture(page);
  const sidebar = await openSidebar(page);
  await expect(sidebar.locator('.thread-name')).toHaveCount(8);
  const title = await page.locator('.conversation-title').textContent();
  await sidebar.getByRole('button', { name: 'More conversations', exact: true }).click();
  await expect(sidebar.locator('.thread-name')).toHaveCount(16);
  expect(
    api.calls.some((row) => row.query.get('unfiled') === 'true' && row.query.get('page') === '2'),
  ).toBe(true);
  expect(api.calls.some((row) => row.query.get('parent_id') === 'research')).toBe(false);
  const research = sidebar.getByRole('treeitem', { name: 'Research', exact: true });
  await research.focus();
  await research.press('ArrowRight');
  await expect(sidebar.getByRole('treeitem', { name: 'Nested notes', exact: true })).toBeVisible();
  await research.press('ArrowDown');
  await expect(sidebar.getByRole('treeitem', { name: 'Nested notes', exact: true })).toBeFocused();
  expect(api.calls.some((row) => row.query.get('parent_id') === 'research')).toBe(true);
  await expect(page.locator('.conversation-title')).toHaveText(title!);
  await sidebar
    .getByRole('searchbox', { name: 'Search conversations', exact: true })
    .fill('Recent 03');
  await sidebar
    .getByRole('searchbox', { name: 'Search conversations', exact: true })
    .press('Enter');
  await expect(sidebar.locator('.thread-name')).toHaveCount(1);
  await expect(sidebar.locator('.thread-name')).toHaveText('Recent 03');
  expect(api.calls.at(-1)?.query.get('q')).toBe('Recent 03');
});
for (const width of [1440, 390])
  test(`grouped sidebar visual ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await groupedFixture(page);
    const sidebar = await openSidebar(page, width < 600);
    await sidebar.getByRole('treeitem', { name: 'Research', exact: true }).click();
    await expect(
      sidebar.getByRole('treeitem', { name: 'Nested notes', exact: true }),
    ).toBeVisible();
    await capture(page, `sidebar-${width}.png`);
    await expect(sidebar.getByRole('alert')).toHaveCount(0);
    const bounds = await page.locator('#conversation-history').boundingBox();
    expect(bounds!.width).toBeLessThanOrEqual(width < 600 ? width : 250);
  });
test('folder create rename and removal preserve conversations with revision bodies', async ({
  page,
}) => {
  const api = await groupedFixture(page);
  const sidebar = await openSidebar(page);
  await sidebar.getByRole('button', { name: 'Conversation options', exact: true }).click();
  await sidebar.getByRole('menuitem', { name: 'New folder', exact: true }).click();
  let dialog = sidebar.getByRole('dialog');
  await dialog.getByLabel('Folder name', { exact: true }).fill('Acceptance folder');
  await dialog.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  const created = api.folders.find((row) => row.name === 'Acceptance folder')!;
  expect(created).toBeTruthy();
  const write = api.calls.find(
    (row) => row.method === 'POST' && row.path.endsWith('/chat/folders'),
  );
  expect(write?.csrf).toBe('synthetic-csrf+token');
  await sidebar
    .getByRole('button', { name: 'Folder actions · Acceptance folder', exact: true })
    .click();
  await sidebar.getByRole('menuitem', { name: 'Rename', exact: true }).click();
  dialog = sidebar.getByRole('dialog');
  await dialog.getByLabel('Folder name', { exact: true }).fill('Renamed folder');
  await dialog.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(
    sidebar.getByRole('treeitem', { name: 'Renamed folder', exact: true }),
  ).toBeVisible();
  expect(
    api.calls.find((row) => row.method === 'PATCH' && row.path.endsWith('/' + created.id))?.body[
      'expected_revision'
    ],
  ).toBe(1);
  await sidebar.getByRole('button', { name: 'Folder actions · Research', exact: true }).click();
  await sidebar.getByRole('menuitem', { name: 'Remove folder', exact: true }).click();
  await sidebar
    .getByRole('dialog')
    .getByRole('button', { name: 'Remove folder', exact: true })
    .click();
  await expect(sidebar.getByRole('treeitem', { name: 'Research', exact: true })).toHaveCount(0);
  expect(api.threads.find((row) => row.id === 'filed')?.folder_id).toBe(null);
  expect(api.folders.find((row) => row.id === 'nested')?.parent_id).toBe(null);
});

test('sidebar touch actions are at least 44px and the boundary control has its own hit area', async ({
  browser,
}) => {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: true });
    const page = await context.newPage();
    try {
      await groupedFixture(page);
      const sidebar = await openSidebar(page, width < 600);
      const controls = sidebar.locator(
        '.icon-button:visible,.text-button:visible,.item-name:visible,.destination:visible',
      );
      for (const control of await controls.all()) {
        const rect = await control.boundingBox();
        expect(rect!.width).toBeGreaterThanOrEqual(44);
        expect(rect!.height).toBeGreaterThanOrEqual(44);
      }
      if (width > 600) {
        const menu = await sidebar
          .getByRole('button', { name: 'Conversation options', exact: true })
          .boundingBox();
        const boundary = await page
          .getByRole('button', { name: 'Hide conversations', exact: true })
          .boundingBox();
        expect(menu!.x + menu!.width).toBeLessThanOrEqual(boundary!.x);
      }
    } finally {
      await context.close();
    }
  }
});
