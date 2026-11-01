// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { openAdministration,  mockService } from './fixtures';
test('primary navigation shares the header and knowledge search appears only in Library', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await mockService(page);
  await page.goto('/library');
  const header = page.locator('ffk-shell .topbar');
  const nav = header.getByRole('navigation', { name: 'Main navigation', exact: true });
  await expect(nav).toBeVisible();
  await expect(
    header.getByRole('searchbox', { name: 'Search your knowledge', exact: true }),
  ).toBeVisible();
  const headerBox = (await header.boundingBox())!;
  expect((await nav.getByRole('button').allTextContents()).map(text => text.trim())).toEqual(['Chat', 'Library', 'My activity']);
  for (const name of ['Chat', 'Library']) {
    const box = (await nav.getByRole('button', { name, exact: true }).boundingBox())!;
    expect(box.y).toBeGreaterThanOrEqual(headerBox.y);
    expect(box.y + box.height).toBeLessThanOrEqual(headerBox.y + headerBox.height);
  }
  await nav.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(header.getByRole('searchbox')).toHaveCount(0);
  await openAdministration(page, 'Activity');
  await expect(header.getByRole('searchbox')).toHaveCount(0);
  await nav.getByRole('button', { name: 'Library', exact: true }).click();
  await expect(header.getByRole('searchbox')).toBeVisible();
  const main = (await page.locator('ffk-shell main').boundingBox())!;
  expect(main.width).toBe(1440);
});
for (const width of [1440, 1024, 820])
  test(`desktop account and Settings contain their controls ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await mockService(page);
    await page.goto('/library');
    const avatar = page.getByRole('button', { name: 'Account menu', exact: true });
    await expect(avatar).toBeVisible();
    const frame = (await avatar.boundingBox())!;
    expect(frame.width).toBeGreaterThanOrEqual(40);
    expect(frame.height).toBeGreaterThanOrEqual(40);
    await avatar.click();
    const account = page.getByRole('menu', { name: 'Account menu', exact: true });
    await expect(account).toBeVisible();
    for (const name of ['Your account', 'API tokens', 'Authorized applications', 'Sign out']) {
      const box = (await account.getByRole('menuitem', { name, exact: true }).boundingBox())!;
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(width);
      expect(box.y + box.height).toBeLessThanOrEqual(800);
    }
    await page.keyboard.press('Escape');
    await expect(avatar).toBeFocused();
    const toggle = page.getByRole('button', { name: 'Open navigation', exact: true });
    if (await toggle.isVisible()) await toggle.click();
    await openAdministration(page, 'Settings');
    const nav = page.getByRole('navigation', { name: 'Settings sections' });
    await expect(nav).toBeVisible();
    const local = (await nav.boundingBox())!,
      footer = (await page.locator('ffk-shell footer').boundingBox())!;
    expect(local.y + local.height).toBeGreaterThanOrEqual(footer.y - 52);
    expect(footer.y + footer.height).toBeLessThanOrEqual(801);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });

test('authenticated avatar loads and a failed image falls back to readable initials', async ({
  page,
}) => {
  await mockService(page);
  const png = await page.evaluate(() => {
    const c = document.createElement('canvas');
    c.width = c.height = 16;
    const ctx = c.getContext('2d')!;
    ctx.fillStyle = '#855414';
    ctx.fillRect(0, 0, 16, 16);
    return c.toDataURL('image/png').split(',')[1];
  });
  await page.route('**/bff/api/v1/profile', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        subject: 'synthetic.reviewer',
        display_name: 'Alexandra Rivera de la Fuente',
        locale: 'en-US',
        time_zone: 'UTC',
        response_language: 'en',
        avatar_version: 'fixture-v1',
      }),
    }),
  );
  await page.route('**/bff/api/v1/profile/avatar', (route) =>
    route.fulfill({ contentType: 'image/png', body: Buffer.from(png, 'base64') }),
  );
  await page.goto('/library');
  const avatar = page.getByRole('button', { name: 'Account menu', exact: true });
  await expect(avatar.locator('img')).toBeVisible();
  expect(await avatar.locator('img').evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(
    16,
  );
  await avatar.locator('img').dispatchEvent('error');
  await expect(avatar.locator('img')).toHaveCount(0);
  await expect(avatar).toHaveText('AR');
});
for (const width of [320, 390])
  test(`mobile sidebar account remains contained ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 680 });
    await mockService(page);
    await page.goto('/library');
    const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
    await menu.click();
    const avatar = page.getByRole('button', { name: 'Your account', exact: true });
    await expect(avatar).toBeVisible();
    const box = (await avatar.boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(36);
    expect(box.y + box.height).toBeLessThanOrEqual(680);
    await page.keyboard.press('Escape');
    await expect(menu).toBeFocused();
    await menu.click();
    await openAdministration(page, 'Settings');
    await expect(
      page.getByRole('combobox', { name: 'Settings section', exact: true }),
    ).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });

test('mobile Library keeps the avatar beside the logo and the search below', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockService(page);
  await page.goto('/library');
  const header = page.locator('ffk-shell .topbar'),
    logo = (await header.locator('.brand').boundingBox())!,
    avatar = (await header
      .getByRole('button', { name: 'Account menu', exact: true })
      .boundingBox())!,
    search = (await header
      .getByRole('searchbox', { name: 'Search your knowledge', exact: true })
      .boundingBox())!;
  expect(Math.abs(logo.y + logo.height / 2 - avatar.y - avatar.height / 2)).toBeLessThan(4);
  expect(search.y).toBeGreaterThan(avatar.y + avatar.height);
  expect((await header.boundingBox())!.height).toBeLessThanOrEqual(132);
});
test('Library rows adapt to a narrow embedded region with touch details', async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    hasTouch: true,
  });
  const page = await context.newPage();
  try {
    await mockService(page);
    await page.goto('/library');
    const list = page.locator('ffk-resource-list');
    await list.evaluate((node) => {
      (node as HTMLElement).style.width = '340px';
    });
    const box = (await list
      .getByRole('button', { name: /Details for/ })
      .first()
      .boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(44);
    expect(box.height).toBeGreaterThanOrEqual(44);
    expect(await list.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);
    expect((await list.locator('.header').boundingBox())!.height).toBe(1);
    await expect(list.getByRole('columnheader', { name: 'Name', exact: true })).toHaveCount(1);
  } finally {
    await context.close();
  }
});
