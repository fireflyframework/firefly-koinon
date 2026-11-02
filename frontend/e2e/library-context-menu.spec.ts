// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockService } from './fixtures';

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
