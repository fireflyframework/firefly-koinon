// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { entry, mockService } from './fixtures';

test('Library menu keeps arrow-key selection until Enter opens the chosen action', async ({
  page,
}) => {
  await mockService(page);
  await page.goto('/library');
  const trigger = page.getByRole('button', {
    name: 'Actions for Research operations',
    exact: true,
  });
  await trigger.focus();
  await page.keyboard.press('Shift+F10');
  const menu = page.getByRole('menu', { name: 'Library actions', exact: true });
  await expect(menu.getByRole('menuitem', { name: 'Open folder', exact: true })).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(menu.getByRole('menuitem', { name: 'Details', exact: true })).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(menu.getByRole('menuitem', { name: 'Edit details', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(menu).toHaveCount(0);
  await expect(
    page.getByRole('dialog').getByRole('textbox', { name: 'Name', exact: true }),
  ).toHaveValue('Research operations');
});

for (const width of [1440, 390]) {
  test(`Library actions use the current folder and remain inside the viewport at ${width}px`, async ({
    page,
  }) => {
    await mockService(page);
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/library');
    const trigger = page.getByRole('button', {
      name: 'Actions for Research operations',
      exact: true,
    });
    await trigger.click();
    const menu = page.getByRole('menu', { name: 'Library actions', exact: true });
    await expect(menu).toBeVisible();
    const bounds = await menu.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(900);
    const directory = process.env['KOINON_CONTEXT_SCREENSHOTS'];
    if (directory) {
      await mkdir(directory, { recursive: true });
      await page.screenshot({
        path: `${directory}/library-actions-${width}.png`,
        animations: 'disabled',
      });
    }
    await page.keyboard.press('Escape');
    await expect(menu).toHaveCount(0);
    await expect(trigger).toBeFocused();
    const folder = page.getByRole('button', { name: 'Research operations', exact: true });
    await folder.click({ button: 'right' });
    await menu.getByRole('menuitem', { name: 'Open folder', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: 'Research operations', exact: true }),
    ).toBeVisible();
    const project = page.getByRole('button', { name: 'Operations intelligence', exact: true });
    await project.focus();
    await page.keyboard.press('Shift+F10');
    await menu.getByRole('menuitem', { name: 'Edit details', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue(
      'Operations intelligence',
    );
  });
}

test('system space context actions retain protection and empty Library creates through the existing form', async ({
  page,
}) => {
  const service = await mockService(page);
  service.rows[0].system_managed = true;
  await page.goto('/library');
  await page
    .getByRole('button', { name: 'Research operations', exact: true })
    .click({ button: 'right' });
  const menu = page.getByRole('menu', { name: 'Library actions', exact: true });
  await expect(menu).toBeVisible();
  await expect(menu.getByRole('menuitem', { name: 'Archive', exact: true })).toHaveCount(0);
  await expect(
    menu.getByRole('menuitem', { name: 'Move Library folder', exact: true }),
  ).toHaveCount(0);
  await page.keyboard.press('Escape');
  await page.locator('.collection-surface').click({ button: 'right', position: { x: 10, y: 1 } });
  await menu.getByRole('menuitem', { name: 'Create a space', exact: true }).click();
  await expect(
    page.getByRole('dialog').getByRole('textbox', { name: 'Name', exact: true }),
  ).toBeVisible();
  expect(service.writes).toHaveLength(0);
});

for (const width of [1440, 390]) {
  for (const count of [0, 1, 25]) {
    test(`Library surface fills available height with ${count} rows at ${width}px`, async ({
      page,
    }) => {
      const service = await mockService(page);
      service.rows.splice(
        0,
        service.rows.length,
        ...Array.from({ length: count }, (_, index) =>
          entry(`space-${index}`, 'workspace', `Space ${index + 1}`, null),
        ),
      );
      await page.setViewportSize({ width, height: 1000 });
      await page.goto('/library');
      await expect(page.locator('.item-count')).toHaveText(
        `${count} ${count === 1 ? 'item' : 'items'}`,
      );
      const surface = page.locator('.collection-surface');
      const bounds = await surface.boundingBox();
      const content = await page.locator('ffk-shell .content').boundingBox();
      expect(bounds!.y + bounds!.height).toBeGreaterThanOrEqual(content!.y + content!.height - 17);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      if (count < 25) {
        await surface.click({ button: 'right', position: { x: 20, y: bounds!.height - 80 } });
        const menu = page.getByRole('menu', { name: 'Library actions', exact: true });
        await expect(
          menu.getByRole('menuitem', { name: 'Create a space', exact: true }),
        ).toBeVisible();
        await expect(
          menu.getByRole('menuitem', { name: 'Upload files', exact: true }),
        ).toBeVisible();
        await page.keyboard.press('Escape');
        await expect(surface).toBeFocused();
      } else {
        await page.getByRole('button', { name: 'Space 25', exact: true }).scrollIntoViewIfNeeded();
        await expect(page.getByRole('button', { name: 'Space 25', exact: true })).toBeVisible();
      }
      const directory = process.env['KOINON_CONTEXT_SCREENSHOTS'];
      if (directory) {
        await mkdir(directory, { recursive: true });
        await page.screenshot({
          path: `${directory}/library-${count}-rows-${width}.png`,
          animations: 'disabled',
        });
      }
    });
  }
}

test('current location menu works with keyboard and a touch-friendly trigger', async ({ page }) => {
  await mockService(page);
  await page.goto('/library');
  const surface = page.locator('.collection-surface');
  await surface.focus();
  await page.keyboard.press('Shift+F10');
  const menu = page.getByRole('menu', { name: 'Library actions', exact: true });
  await expect(menu.getByRole('menuitem', { name: 'Create a space', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(surface).toBeFocused();
  const trigger = page.getByRole('button', { name: 'Actions for this location', exact: true });
  await trigger.click();
  await expect(menu).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(trigger).toBeFocused();
});

test('location creation and direct upload use the current folder destination', async ({ page }) => {
  const service = await mockService(page);
  await page.goto('/library');
  await page.getByRole('button', { name: 'Research operations', exact: true }).click();
  await page.getByRole('button', { name: 'Operations intelligence', exact: true }).click();
  await page.getByRole('button', { name: 'Reference library', exact: true }).click();
  const trigger = page.getByRole('button', { name: 'Actions for this location', exact: true });
  const menu = page.getByRole('menu', { name: 'Library actions', exact: true });
  await trigger.click();
  await menu.getByRole('menuitem', { name: 'Create a folder', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: 'Name', exact: true }).fill('Local child');
  await dialog.getByRole('button', { name: 'Create folder', exact: true }).click();
  expect(
    service.writes.find(
      (write) =>
        write.method === 'POST' && (write.body as { name?: string }).name === 'Local child',
    )?.body,
  ).toMatchObject({ parent_id: 'collection-one', kind: 'collection' });
  await trigger.click();
  await menu.getByRole('menuitem', { name: 'Upload files', exact: true }).click();
  await expect(dialog.getByRole('heading', { name: 'Upload files', exact: true })).toBeVisible();
  await expect(dialog.locator('.upload-location')).toContainText('Reference library');
  await expect(dialog.locator('.upload-folder-picker')).toHaveCount(0);
});

for (const width of [320, 390]) {
  test(`folder type filter leaves the sort selection readable at ${width}px`, async ({ page }) => {
    await mockService(page);
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/library');
    await page.getByRole('button', { name: 'Research operations', exact: true }).click();
    await page.getByRole('button', { name: 'Operations intelligence', exact: true }).click();
    await page.getByRole('button', { name: 'Reference library', exact: true }).click();
    await expect(page.getByRole('combobox', { name: 'Filter library type' })).toBeVisible();
    const sort = page.getByRole('combobox', { name: 'Sort library items' });
    const bounds = await sort.boundingBox();
    const count = await page.locator('.item-count').boundingBox();
    expect(bounds!.width).toBeGreaterThanOrEqual(100);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(count!.x);
    await sort.selectOption('updated_at.desc');
    await expect(sort).toHaveValue('updated_at.desc');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });
}
