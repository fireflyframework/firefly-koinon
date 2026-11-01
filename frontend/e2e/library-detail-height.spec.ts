// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockService } from './fixtures';
async function capture(page: Page, name: string) {
  const directory = process.env['KOINON_DETAIL_SCREENSHOTS'];
  if (directory) {
    await mkdir(directory, { recursive: true });
    await page.screenshot({ path: `${directory}/${name}.png`, animations: 'disabled' });
  }
}
for (const width of [1440, 390]) {
  test(`a single folder keeps details full height and metadata reachable at ${width}px`, async ({
    page,
  }) => {
    const service = await mockService(page);
    service.rows[0].metadata = { final_note: 'Final retained metadata value' };
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/library');
    await page
      .getByRole('button', { name: 'Details for Research operations', exact: true })
      .click();
    const details = page.getByRole(width > 1000 ? 'complementary' : 'dialog', {
      name: 'Resource details',
      exact: true,
    });
    await expect(details).toBeVisible();
    await capture(page, `single-folder-${width}`);
    const bounds = await details.boundingBox();
    const footer = await page.locator('footer').boundingBox();
    if (width > 1000) expect(bounds!.y + bounds!.height).toBeGreaterThanOrEqual(footer!.y - 20);
    else expect(bounds!.y + bounds!.height).toBeGreaterThanOrEqual(975);
    await details.getByText('Technical details', { exact: true }).click();
    const metadata = details.getByText('Final retained metadata value', { exact: true });
    await metadata.scrollIntoViewIfNeeded();
    await expect(metadata).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    if (width < 1000) {
      await details.getByRole('button', { name: 'Close details', exact: true }).focus();
      await page.keyboard.press('Escape');
      await expect(details).toHaveCount(0);
      await expect(
        page.getByRole('button', { name: 'Details for Research operations', exact: true }),
      ).toBeFocused();
    }
  });
}

for (const width of [1440, 390]) {
  test(`long details remain scrollable and final metadata is reachable at ${width}px`, async ({
    page,
  }) => {
    const service = await mockService(page);
    service.rows[0].metadata = Object.fromEntries(
      Array.from({ length: 32 }, (_, i) => [`retained_field_${i}`, `Retained metadata value ${i}`]),
    );
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/library');
    await page
      .getByRole('button', { name: 'Details for Research operations', exact: true })
      .click();
    const details = page.getByRole(width > 1000 ? 'complementary' : 'dialog', {
      name: 'Resource details',
      exact: true,
    });
    await details.getByText('Technical details', { exact: true }).click();
    const last = details.getByText('Retained metadata value 31', { exact: true });
    await last.scrollIntoViewIfNeeded();
    await expect(last).toBeVisible();
    const end = await last.boundingBox();
    if (width > 1000) {
      const footer = await page.locator('footer').boundingBox();
      expect(end!.y + end!.height).toBeLessThanOrEqual(footer!.y);
    } else expect(end!.y + end!.height).toBeLessThanOrEqual(1000);
    await capture(page, `long-details-${width}`);
  });
}
