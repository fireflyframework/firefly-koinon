// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { mkdir } from 'node:fs/promises';
import { expect, test, type Page } from '@playwright/test';
import { mockService, openAdministration, context } from './fixtures';
async function capture(page: Page, name: string) {
  const directory = process.env['KOINON_SETTINGS_CAPTURE_DIR'];
  if (!directory) return;
  await mkdir(directory, { recursive: true });
  await page.screenshot({ path: `${directory}/${name}.png`, animations: 'disabled' });
}
async function section(page: Page, id: string, label: string) {
  const select = page.getByRole('combobox', { name: 'Settings section', exact: true });
  if (await select.isVisible()) await select.selectOption(id);
  else await page.getByRole('button', { name: label, exact: true }).click();
}
for (const width of [1440, 390]) {
  for (const spanish of [false, true]) {
    test(`normal Settings opens the task overview at ${width}px in ${spanish ? 'Spanish' : 'English'}`, async ({ page }) => {
      await mockService(page);
      if (spanish) await page.route('**/bff/api/v1/profile', route => route.fulfill({ json: { subject: context.subject, display_name: 'Alex Rivera', locale: 'es-ES', time_zone: 'UTC', response_language: 'es', avatar_url: null, avatar_version: null } }));
      await page.setViewportSize({ width, height: 900 });
      await page.goto('/library');
      await openAdministration(page, spanish ? 'Configuración' : 'Settings');
      const overview = page.locator('ffk-knowledge-overview');
      await expect(overview).toBeVisible();
      await expect(overview.getByRole('heading', { name: spanish ? 'Conocimiento e IA' : 'Knowledge & AI', exact: true })).toBeVisible();
      if (width < 760) await expect(page.getByRole('combobox', { name: spanish ? 'Sección de configuración' : 'Settings section', exact: true })).toHaveValue('knowledge');
      else await expect(page.getByRole('button', { name: spanish ? 'Resumen' : 'Overview', exact: true })).toHaveAttribute('aria-current', 'page');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await capture(page, `knowledge-ai-overview-${width}-${spanish ? 'es' : 'en'}`);
      await page.getByRole('button', { name: spanish ? 'Gestionar conexiones' : 'Manage connections', exact: true }).click();
      await expect(page.getByRole('heading', { name: spanish ? 'Conexiones de modelos' : 'Model connections', exact: true })).toBeVisible();
    });
  }
  test(`answer policy remains separate and sidebar departure preserves a draft at ${width}px`, async ({ page }) => {
    const service = await mockService(page);
    await page.route('**/bff/api/v1/tenants/*/agents**', route => route.fulfill({ json: { items: [], total: 0, pages: 1, page: 1, page_size: 100 } }));
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/library');
    await openAdministration(page, 'Settings');
    await page.getByRole('button', { name: 'Configure answers', exact: true }).click();
    const panel = page.locator('ffk-knowledge-behavior');
    await expect(panel.getByRole('heading', { name: 'Knowledge answers', exact: true })).toBeInViewport();
    await expect(page.locator('ffk-knowledge-models')).toHaveCount(0);
    await panel.getByText('Document search and answers', { exact: true }).click();
    const field = panel.locator('input[name="documents.retrieval_top_k"]');
    const previous = await field.inputValue();
    const next = previous === '18' ? '19' : '18';
    await field.fill(next);
    const inputBox = await field.boundingBox(), barBox = await panel.locator('footer').boundingBox();
    expect(inputBox!.y + inputBox!.height + 2).toBeLessThanOrEqual(barBox!.y);
    await panel.locator('section').evaluate(element => element.closest('.settings-content')!.scrollTop = 0);
    await capture(page, `knowledge-answers-${width}`);
    await section(page, 'knowledge', 'Overview');
    const review = page.getByRole('region', { name: 'Leave this settings editor?', exact: true });
    await expect(review).toBeVisible();
    await expect(review.getByRole('button', { name: 'Keep editing', exact: true })).toBeFocused();
    await review.getByRole('button', { name: 'Keep editing', exact: true }).click();
    await expect(field).toHaveValue(next);
    await expect(review).toHaveCount(0);
    await section(page, 'knowledge', 'Overview');
    await review.getByRole('button', { name: 'Leave editor', exact: true }).click();
    await expect(page.locator('ffk-knowledge-overview')).toBeVisible();
    expect(service.writes).toHaveLength(0);
    await page.getByRole('button', { name: 'Configure assistant', exact: true }).click();
    await expect(page.locator('ffk-organization-chat-settings')).toBeVisible();
    await expect(page.locator('.assistant-first-start')).toBeVisible();
    const firstStart = await page.locator('.assistant-first-start').boundingBox(), chat = await page.locator('ffk-organization-chat-settings').boundingBox();
    expect(firstStart!.y + firstStart!.height).toBeLessThanOrEqual(chat!.y);
    await expect(page.locator('.settings-content > .error')).toHaveCount(0);
    await expect(page.locator('ffk-organization-chat-settings').getByRole('alert')).toHaveCount(0);
    await expect(page.locator('.additional-agents')).not.toHaveAttribute('open');
    await capture(page, `organization-assistant-${width}`);
  });
}
