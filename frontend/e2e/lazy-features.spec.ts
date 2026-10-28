// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { expect, test } from '@playwright/test';
import { mockService } from './fixtures';

test('Library boot keeps source coordinates and OpenUI outside the initial JavaScript', async ({
  page,
}) => {
  const loaded: string[] = [];
  page.on('response', (response) => {
    if (response.request().resourceType() === 'script') loaded.push(response.url());
  });
  await mockService(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Library', exact: true })).toBeVisible();
  const scripts = await Promise.all(
    loaded.map(async (url) => (await page.request.get(url)).text()),
  );
  expect(scripts.join('\n')).not.toContain('ffk-table-coordinates');
  expect(scripts.join('\n')).not.toContain('ffk-openui-answer');
});

test('opening a new chat waits for an answer before downloading OpenUI', async ({ page }) => {
  const loaded: string[] = [];
  page.on('response', (response) => {
    if (response.request().resourceType() === 'script') loaded.push(response.url());
  });
  await mockService(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Chat', exact: true })).toBeAttached();
  const scripts = await Promise.all(
    loaded.map(async (url) => (await page.request.get(url)).text()),
  );
  expect(scripts.join('\n')).not.toContain('ffk-openui-answer');
});
