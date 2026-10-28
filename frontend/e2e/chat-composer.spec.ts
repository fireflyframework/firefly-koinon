// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Design fixtures exercise browser interactions without an upload or model call.
import { test, expect } from '@playwright/test';
import { resolve } from 'node:path';
const captures = resolve('../../../outputs');
for (const width of [1440, 720, 390]) {
  test(`Composer files, menu and reflow ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 960 });
    await page.goto('/design/');
    const image = Buffer.from(
      await page.evaluate(() => {
        const canvas = document.createElement('canvas');
        canvas.width = 400;
        canvas.height = 260;
        const context = canvas.getContext('2d')!;
        context.fillStyle = '#f5f1e8';
        context.fillRect(0, 0, 400, 260);
        context.fillStyle = '#ffb34a';
        context.fillRect(28, 28, 44, 7);
        context.fillStyle = '#272820';
        context.font = '24px sans-serif';
        context.fillText('Service review', 28, 78);
        context.fillStyle = '#d9d5cc';
        for (let y = 110; y < 220; y += 25) context.fillRect(28, y, y === 210 ? 190 : 340, 7);
        return canvas.toDataURL('image/png').split(',')[1];
      }),
      'base64',
    );
    await page.getByRole('button', { name: 'Chat composer', exact: true }).click();
    const composer = page.locator('ffk-chat-composer');
    const input = composer.getByRole('textbox', {
      name: 'Message koinon',
      exact: true,
    });
    await expect(input).toBeVisible();
    expect((await composer.boundingBox())!.height).toBeLessThanOrEqual(width > 600 ? 48 : 96);
    await composer.screenshot({
      path: resolve(captures, `koinon-chat-composer-compact-text-${width}.png`),
    });
    const add = composer.getByRole('button', { name: 'Add context', exact: true });
    await add.click();
    const menu = page.getByRole('menu', { name: 'Add context', exact: true });
    await expect(menu).toBeVisible();
    await expect(page.getByRole('menuitem', { name: /Attach files/ })).toBeFocused();
    const box = await menu.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    await page.keyboard.press('Escape');
    await expect(add).toBeFocused();
    await add.click();
    await page.keyboard.press('Tab');
    await expect(menu).toHaveCount(0);
    await expect(input).toBeFocused();
    await add.click();
    await page.keyboard.press('Shift+Tab');
    await expect(menu).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Grid', exact: true })).toBeFocused();
    await composer.locator('input[type=file]').setInputFiles([
      { name: 'Service-review.png', mimeType: 'image/png', buffer: image },
      {
        name: 'Operations-notes.md',
        mimeType: 'text/markdown',
        buffer: Buffer.from('# Review\nReview service escalation changes.'),
      },
    ]);
    await expect(composer.getByRole('listitem')).toHaveCount(2);
    await expect(composer.locator('img')).toBeVisible();
    const preview = await composer.locator('.attachment-preview').first().boundingBox();
    const thumbnail = await composer.locator('img').boundingBox();
    expect(thumbnail!.y + thumbnail!.height).toBeLessThanOrEqual(preview!.y + preview!.height);
    await expect(composer.getByRole('button', { name: 'Send', exact: true })).toBeDisabled();
    await page.getByRole('combobox', { name: 'Preview state', exact: true }).selectOption('ready');
    await expect(composer.getByRole('button', { name: 'Send', exact: true })).toBeEnabled();
    expect((await composer.boundingBox())!.height).toBeLessThanOrEqual(width > 600 ? 205 : 235);
    console.log(
      `Composer ${width}px: ${Math.round((await composer.boundingBox())!.height)}px with files`,
    );
    await composer.screenshot({
      path: resolve(captures, `koinon-chat-composer-compact-files-${width}.png`),
    });
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
      .toBe(true);
    await page.screenshot({
      path: resolve(captures, `koinon-chat-composer-${width}.png`),
      fullPage: true,
    });
    await add.click();
    await expect(menu).toBeVisible();
    await page.screenshot({
      path: resolve(captures, `koinon-chat-composer-menu-${width}.png`),
      fullPage: true,
    });
    await page.keyboard.press('Escape');
    await composer
      .getByRole('button', { name: 'Remove file: Service-review.png', exact: true })
      .click();
    await expect(composer.getByRole('listitem')).toHaveCount(1);
    const dropped = await page.evaluateHandle(() => {
      const transfer = new DataTransfer();
      transfer.items.add(new File(['Review notes'], 'Dropped-notes.txt', { type: 'text/plain' }));
      return transfer;
    });
    await composer.locator('form').dispatchEvent('dragenter', { dataTransfer: dropped });
    await expect(composer.locator('.drop-prompt')).toBeVisible();
    await composer.locator('form').dispatchEvent('drop', { dataTransfer: dropped });
    await expect(composer.getByRole('listitem')).toHaveCount(2);
    await expect(composer.locator('.drop-prompt')).toHaveCount(0);
    await dropped.dispose();
    await input.fill('One line');
    const initial = (await input.boundingBox())!.height;
    await input.fill(Array(25).fill('A longer question about the selected knowledge.').join('\n'));
    expect((await input.boundingBox())!.height).toBeGreaterThan(initial);
    expect((await input.boundingBox())!.height).toBeLessThanOrEqual(220);
  });
}
test('composer adapts to a narrow embedded host and preserves touch target sizes', async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    hasTouch: true,
  });
  const page = await context.newPage();
  try {
    await page.goto('/design/');
    await page.getByRole('button', { name: 'Chat composer', exact: true }).click();
    await page.locator('.stage').evaluate((node) => {
      (node as HTMLElement).style.width = '360px';
    });
    const composer = page.locator('ffk-chat-composer');
    expect(
      await composer.locator('textarea').evaluate((node) => getComputedStyle(node).fontSize),
    ).toBe('16px');
    await expect(composer.locator('.knowledge-context')).toHaveCount(0);
    await composer.locator('input[type=file]').setInputFiles({
      name: 'Notes.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('Private review notes'),
    });
    expect(
      (await composer
        .getByRole('button', { name: 'Remove file: Notes.md', exact: true })
        .boundingBox())!.width,
    ).toBeGreaterThanOrEqual(44);
    expect(
      (await composer.getByRole('button', { name: 'Send', exact: true }).boundingBox())!.width,
    ).toBeGreaterThanOrEqual(44);
    expect(await composer.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);
    await composer.screenshot({
      path: resolve(captures, 'koinon-chat-composer-embedded-touch.png'),
    });
  } finally {
    await context.close();
  }
});
