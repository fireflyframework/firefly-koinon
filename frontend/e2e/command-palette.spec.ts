// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { mockService, fixtures } from './fixtures';

test('New conversation opens a clean draft from Library even when history exists', async ({
  page,
}) => {
  await mockService(page, { organizationAgent: 'guide' });
  const thread = {
    id: 'old-thread',
    title: 'Saved discussion',
    scope: {},
    created_at: '2026-10-27T10:00:00Z',
    updated_at: '2026-10-27T10:00:00Z',
    title_source: 'manual',
    revision: 1,
    folder_id: null,
    archived_at: null,
  };
  let writes = 0;
  await page.route('**/bff/api/v1/tenants/*/**', (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (request.method() === 'POST') ++writes;
    if (path.endsWith('/agents'))
      return route.fulfill({
        json: { items: [{ id: 'guide', name: 'Guide', status: 'ready', checks: [] }] },
      });
    if (path.endsWith('/chat/threads'))
      return route.fulfill({ json: { items: [thread], page: 1, pages: 1, total: 1 } });
    if (path.endsWith('/chat/threads/old-thread')) return route.fulfill({ json: thread });
    if (path.endsWith('/messages'))
      return route.fulfill({
        json: {
          items: [
            {
              id: 'old-answer',
              role: 'assistant',
              text: 'Old answer',
              status: 'completed',
              artifacts: [],
              citations: [],
              created_at: thread.created_at,
            },
          ],
          next_cursor: null,
        },
      });
    return route.fallback();
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Search and commands', exact: true }).click();
  await page.getByRole('option', { name: 'New conversation', exact: true }).click();
  const editor = page.getByRole('textbox', { name: 'Message koinon', exact: true });
  await expect(editor).toBeEnabled();
  await expect(editor).toHaveValue('');
  await expect(page.getByText('Old answer', { exact: true })).toHaveCount(0);
  expect(writes).toBe(0);
  await editor.fill('Unsent draft');
  await editor.press('Control+k');
  await page.getByRole('option', { name: 'New conversation', exact: true }).click();
  await expect(editor).toHaveValue('');
  expect(writes).toBe(0);
});

test('palette searches scoped server results and opens a resource with keyboard navigation', async ({
  page,
}) => {
  await mockService(page, { organizationAgent: 'guide' });
  const searches: Record<string, string>[] = [];
  await page.route('**/bff/api/v1/tenants/*/catalog?**', async (route) => {
    const url = new URL(route.request().url());
    if (!url.searchParams.get('q')) return route.fallback();
    searches.push(Object.fromEntries(url.searchParams));
    return route.fulfill({
      json: {
        items: [fixtures.find((row) => row.id === 'document-one')],
        page: 1,
        pages: 1,
        total: 1,
        page_size: 8,
      },
    });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Search and commands', exact: true }).focus();
  await page.keyboard.press('Control+k');
  const dialog = page.getByRole('dialog', { name: 'Search and navigate', exact: true });
  const input = dialog.getByRole('combobox');
  await expect(input).toBeFocused();
  await input.fill('Service operating');
  await expect(dialog.getByRole('option', { name: /Service operating policy/ })).toBeVisible();
  expect(searches.at(-1)).toMatchObject({
    q: 'Service operating',
    page: '1',
    page_size: '8',
    view: 'library',
  });
  await input.press('Home');
  await input.press('Enter');
  await expect(dialog).not.toBeVisible();
  await expect(
    page
      .locator('ffk-inspector')
      .getByRole('heading', { name: 'Service operating policy.pdf', exact: true }),
  ).toBeVisible();
});

for (const width of [320, 390]) {
  test(`mobile commands fit the header and return focus after Escape at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 800 });
    await mockService(page, { organizationAgent: 'guide' });
    await page.goto('/');
    const trigger = page.getByRole('button', { name: 'Search and commands', exact: true });
    await trigger.click();
    const dialog = page.getByRole('dialog', { name: 'Search and navigate', exact: true });
    await expect(dialog).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await dialog.getByRole('combobox').press('Escape');
    await expect(dialog).not.toBeVisible();
    await expect(trigger).toBeFocused();
    const boxes = await page
      .locator('ffk-shell .brand, ffk-shell .header-actions')
      .evaluateAll((nodes) =>
        nodes.map((node) => {
          const r = node.getBoundingClientRect();
          return { left: r.left, right: r.right };
        }),
      );
    expect(boxes[0].right).toBeLessThanOrEqual(boxes[1].left);
  });
}
