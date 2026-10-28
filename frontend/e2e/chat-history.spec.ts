// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled HTTP fixtures qualify frontend requests, not live model behavior.
import { test, expect } from '@playwright/test';
import { mockService } from './fixtures';
import type { ChatThread } from '@fireflyframework/koinon-sdk';
test('history requests server pages and filters, preserves the selected scope, and restores an archived thread', async ({
  page,
}) => {
  await mockService(page);
  const rows: ChatThread[] = Array.from({ length: 51 }, (_, index) => ({
    id: `history-${index + 1}`,
    title: index === 25 ? 'Policy review' : `Conversation ${index + 1}`,
    title_source: 'manual',
    revision: 1,
    folder_id: null,
    archived_at: null,
    scope: {},
    created_at: '2026-10-26T10:00:00Z',
    updated_at: '2026-10-26T10:00:00Z',
  }));
  const archived: ChatThread = {
    ...rows[0],
    id: 'archived-one',
    title: 'Policy archive',
    revision: 4,
    archived_at: '2026-10-26T12:00:00Z',
  };
  const lists: Record<string, string>[] = [];
  const updates: unknown[] = [];
  let restored = false;
  let modelRequests = 0;
  await page.route('**/bff/api/v1/tenants/*/**', async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname;
    const json = (body: unknown) =>
      route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    if (path.endsWith('/agents'))
      return json({
        items: [{ id: 'guide', name: 'Knowledge guide', status: 'ready', checks: [] }],
      });
    if (path.endsWith('/chat/threads')) {
      lists.push(Object.fromEntries(url.searchParams));
      const query = (url.searchParams.get('q') ?? '').toLowerCase(),
        selectedPage = Number(url.searchParams.get('page') ?? 1),
        pageSize = Number(url.searchParams.get('page_size') ?? 25);
      const all =
        url.searchParams.get('status') === 'archived'
          ? restored
            ? []
            : [archived]
          : [...rows, ...(restored ? [{ ...archived, revision: 5, archived_at: null }] : [])];
      const selected = all.filter((row) => row.title.toLowerCase().includes(query));
      return json({
        items: selected.slice((selectedPage - 1) * pageSize, selectedPage * pageSize),
        page: selectedPage,
        page_size: pageSize,
        total: selected.length,
        pages: Math.ceil(selected.length / pageSize),
      });
    }
    if (path.endsWith('/messages')) return json({ items: [], next_cursor: null });
    if (path.endsWith('/chat/threads/archived-one') && request.method() === 'PATCH') {
      updates.push(request.postDataJSON());
      restored = true;
      return json({ ...archived, revision: 5, archived_at: null });
    }
    if (path.endsWith('/runs')) ++modelRequests;
    return route.fallback();
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  const history = page.locator('.conversation-list');
  await expect(page.getByRole('heading', { name: 'Conversation 1', exact: true })).toBeVisible();
  for (let pageNumber = 2; pageNumber <= 4; pageNumber++)
    await history.getByRole('button', { name: 'More conversations', exact: true }).click();
  await expect(history.getByRole('button', { name: 'Policy review', exact: true })).toBeVisible();
  expect(
    lists.some(
      (query) => query['page'] === '4' && query['page_size'] === '8' && query['unfiled'] === 'true',
    ),
  ).toBe(true);
  await expect(page.getByRole('heading', { name: 'Conversation 1', exact: true })).toBeVisible();
  const search = history.getByRole('searchbox', { name: 'Search conversations', exact: true });
  await search.fill('Policy');
  await search.press('Enter');
  await expect(history.getByRole('button', { name: 'Policy review', exact: true })).toBeVisible();
  expect(lists.at(-1)).toMatchObject({ q: 'Policy', page: '1', page_size: '12', status: 'active' });
  await history.getByRole('button', { name: 'Conversation options', exact: true }).click();
  await history.getByRole('menuitem', { name: 'Archived conversations', exact: true }).click();
  await history.getByRole('button', { name: 'Policy archive', exact: true }).click();
  const editor = page.getByRole('textbox', { name: 'Message koinon', exact: true });
  await expect(editor).toBeDisabled();
  await page.getByRole('button', { name: 'Restore conversation', exact: true }).click();
  await expect(editor).toBeEnabled();
  await history.getByRole('button', { name: 'Back to active', exact: true }).click();
  await expect(history.getByRole('button', { name: 'Policy archive', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Policy archive', exact: true })).toBeVisible();
  expect(updates).toEqual([{ archived: false, expected_revision: 4 }]);
  expect(modelRequests).toBe(0);
});
