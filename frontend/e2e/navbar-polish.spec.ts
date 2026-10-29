// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// Controlled fixtures qualify navbar composition, native selection and accessible navigation.
import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { context, mockService } from './fixtures';
const longOrganization = 'International research and knowledge operations — Europe & Americas';
for (const width of [1440, 390])
  test.describe(`navbar composition ${width}`, () => {
    test.use({ viewport: { width, height: 1000 }, hasTouch: width === 390 });
    test('keeps section icons, native organization choice and keyboard navigation coherent', async ({
      page,
    }) => {
      await mockService(page);
      const identity = structuredClone(context);
      identity.tenants[0].name = longOrganization;
      await page.route('**/bff/api/v1/context', (route) => route.fulfill({ json: identity }));
      await page.goto('/');
      const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
      if (width === 390) await menu.click();
      const navigation = page.getByRole('navigation', { name: 'Main navigation', exact: true });
      for (const label of ['Library', 'Chat', 'Activity', 'Settings']) {
        const button = navigation.getByRole('button', { name: label, exact: true });
        await expect(button).toHaveAccessibleName(label);
        const icon = button.locator('ffk-icon');
        await expect(icon).toBeVisible();
        await expect(icon.locator('svg')).toHaveAttribute('aria-hidden', 'true');
        const size = await icon.boundingBox();
        expect(size!.width).toBeGreaterThanOrEqual(16);
        expect(size!.width).toBeLessThanOrEqual(18);
        expect(size!.height).toBe(size!.width);
      }
      await expect(
        navigation.getByRole('button', { name: 'Library', exact: true }),
      ).toHaveAttribute('aria-current', 'page');
      const organization = page.getByRole('combobox', { name: 'Organization', exact: true });
      await expect(organization).toHaveValue('tenant-one');
      await expect(organization).toHaveAttribute('title', longOrganization);
      await expect(organization.locator('option[value=tenant-one]')).toHaveText(longOrganization);
      const label = organization.locator('..');
      expect(await label.evaluate((node) => node.tagName)).toBe('LABEL');
      const box = await label.boundingBox();
      expect(box!.height).toBeGreaterThanOrEqual(44);
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(width);
      await organization.focus();
      await expect(organization).toBeFocused();
      await organization.selectOption('tenant-two');
      await expect(organization).toHaveValue('tenant-two');
      await organization.selectOption('tenant-one');
      await expect(organization).toHaveValue('tenant-one');
      if (width === 390 && !(await navigation.isVisible())) await menu.click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      const directory = resolve(
        process.env['KOINON_UI_CAPTURE_DIR'] ?? 'test-results/navbar-polish',
      );
      await mkdir(directory, { recursive: true });
      await page.screenshot({
        path: resolve(directory, `navbar-organization-${width}.png`),
        animations: 'disabled',
      });
      const chat = navigation.getByRole('button', { name: 'Chat', exact: true });
      await chat.focus();
      await page.keyboard.press('Enter');
      if (width === 390) await menu.click();
      await expect(navigation.getByRole('button', { name: 'Chat', exact: true })).toHaveAttribute(
        'aria-current',
        'page',
      );
    });
  });
