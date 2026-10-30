// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mockService } from './fixtures';
async function openDirectory(page: Page, width: number) {
  await page.setViewportSize({ width, height: 960 });
  await mockService(page);
  const queries: URLSearchParams[] = [];
  await page.route('**/bff/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.endsWith('/organization/people')) return route.fallback();
    queries.push(url.searchParams);
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        page: Number(url.searchParams.get('page') || 1),
        page_size: 25,
        total: 0,
        pages: 0,
      }),
    });
  });
  await page.goto('/');
  if (width < 700) await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  if (width < 700)
    await page.getByLabel('Settings section', { exact: true }).selectOption('people');
  else await page.getByRole('button', { name: 'People', exact: true }).click();
  await expect(page.locator('ffk-organization-directory h2')).toHaveText('People');
  await expect.poll(() => queries.length).toBe(1);
  return queries;
}
test('mobile filters disclose by keyboard, preserve explicit apply and return focus', async ({
  page,
}) => {
  const queries = await openDirectory(page, 390);
  const directory = page.locator('ffk-organization-directory');
  const toggle = directory.getByRole('button', { name: 'Filters', exact: true });
  const name = directory.getByRole('textbox', { name: 'Name', exact: true });
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(toggle).toHaveAttribute('aria-controls', 'organization-people-filters');
  await expect(name).toBeHidden();
  await toggle.focus();
  await page.keyboard.press('Enter');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Tab');
  await expect(name).toBeFocused();
  await name.fill('Draft');
  await page.keyboard.press('Escape');
  await expect(name).toBeHidden();
  await expect(toggle).toBeFocused();
  expect(queries).toHaveLength(1);
  await page.keyboard.press('Enter');
  await page.keyboard.press('Tab');
  await name.fill('Alex');
  await name.press('Enter');
  await expect.poll(() => queries.at(-1)?.get('q')).toBe('Alex');
  expect(queries.at(-1)?.get('page')).toBe('1');
  await expect(name).toBeHidden();
  await expect(toggle).toBeFocused();
  await expect(toggle.locator('.filter-count')).toHaveText('1');
  await expect(toggle).toHaveAttribute('aria-describedby', 'organization-people-filter-status');
  await page.keyboard.press('Enter');
  await directory.getByRole('button', { name: 'Clear filters', exact: true }).click();
  await expect.poll(() => queries.at(-1)?.get('q')).toBe('');
  await expect(toggle).toBeFocused();
  await expect(toggle.locator('.filter-count')).toHaveCount(0);
});
test('desktop keeps the filter grid visible before and after applying a filter', async ({
  page,
}) => {
  const queries = await openDirectory(page, 1440);
  const directory = page.locator('ffk-organization-directory');
  const name = directory.getByRole('textbox', { name: 'Name', exact: true });
  const title = directory.getByRole('textbox', { name: 'Job title', exact: true });
  await expect(directory.locator('.people-filter-toggle')).toBeHidden();
  await expect(name).toBeVisible();
  await expect(title).toBeVisible();
  const nameBox = await name.boundingBox(),
    titleBox = await title.boundingBox();
  expect(nameBox).not.toBeNull();
  expect(titleBox).not.toBeNull();
  expect(titleBox!.x).toBeGreaterThan(nameBox!.x);
  expect(titleBox!.y).toBe(nameBox!.y);
  await name.fill('Alex');
  await name.press('Enter');
  await expect.poll(() => queries.at(-1)?.get('q')).toBe('Alex');
  await expect(name).toBeVisible();
  await expect(title).toBeVisible();
  await expect(directory.locator('.people-filter-toggle')).toBeHidden();
});
