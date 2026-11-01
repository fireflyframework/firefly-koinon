// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// Controlled saved-chat receipts qualify interface behavior, not a live model or repository.
import { test, expect, type Page } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService, context } from './fixtures';
async function open(page: Page, spanish = false, multiple = false, catalogOnly = false) {
  await mockService(page, { organizationAgent: 'agent' });
  const reads: string[] = [];
  const stamp = '2026-10-29T10:00:00Z';
  const thread = {
    id: 'receipt-thread',
    title: 'Recorded policy review',
    title_source: 'manual',
    scope: {},
    revision: 1,
    folder_id: null,
    archived_at: null,
    created_at: stamp,
    updated_at: stamp,
  };
  if (spanish)
    await page.route('**/bff/api/v1/profile', (route) =>
      route.fulfill({
        json: {
          subject: context.subject,
          display_name: 'Alex Rivera',
          locale: 'es-ES',
          time_zone: 'UTC',
          response_language: 'es',
          avatar_url: null,
          avatar_version: null,
        },
      }),
    );
  await page.route('**/bff/api/v1/tenants/*/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    reads.push(path);
    const json = (value: unknown) => route.fulfill({ json: value });
    if (path.endsWith('/chat/threads'))
      return json({ items: [thread], total: 1, page: 1, page_size: 25, pages: 1 });
    if (path.endsWith('/chat/threads/receipt-thread')) return json(thread);
    if (path.endsWith('/messages'))
      return json({
        items: [
          {
            id: 'receipt-answer',
            run_id: 'receipt-run',
            role: 'assistant',
            status: 'completed',
            text: 'This saved answer uses the recorded policy.',
            citations: [],
            artifacts: [],
            created_at: stamp,
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
      });
    if (path.endsWith('/agents'))
      return json({
        items: [
          {
            id: 'agent',
            name: 'Recorded guide',
            provider_id: 'provider',
            model_id: 'recorded-model',
            tools: [],
            scope: {},
            instructions: '',
            enabled: true,
            configured: true,
            can_run: true,
            status: 'ready',
            revision: 1,
            checks: [],
          },
        ],
      });
    if (path.endsWith('/chat/runs/receipt-run/audit'))
      return json({
        run_id: 'receipt-run',
        provenance_status: 'recorded',
        source_provenance_complete: true,
        generations: [],
        native_reads: [],
        sql_attempts: [],
        sources:
          multiple || catalogOnly
            ? [
                {
                  id: 'catalog-source',
                  asset_id: 'document',
                  kind: 'document',
                  title: 'Recorded operating policy.pdf',
                  quote: 'The recorded policy requires an annual service review.',
                  availability: 'available',
                },
              ]
            : [],
        private_files: catalogOnly
          ? []
          : [
              {
                id: 'private-source',
                filename: 'Service review notes.txt',
                media_type: 'text/plain',
                sha256: 'a'.repeat(64),
                used_revision: 2,
                availability: 'available',
              },
            ],
      });
    if (path.endsWith('/attachments/capabilities'))
      return json({
        storage: { available: true },
        database: { available: true },
        extraction: { available: true },
        formats: [
          {
            kind: 'document',
            media_type: 'text/plain',
            extensions: ['.txt'],
            extraction: { available: true },
          },
        ],
        limits: {
          max_file_bytes: 1048576,
          max_image_bytes: 1048576,
          max_selected: 10,
          max_thread_files: 20,
          max_thread_bytes: 20971520,
          max_model_text_chars: 10000,
          max_model_binary_bytes: 1048576,
          extraction_timeout_seconds: 30,
          ttl_seconds: 3600,
        },
        promotion: {},
      });
    if (path.endsWith('/activity'))
      return json({ items: [], total: 0, page: 1, page_size: 25, pages: 0 });
    return route.fallback();
  });
  await page.goto('/library');
  await expect(
    page.getByRole('button', { name: /^(Account menu|Menú de cuenta)$/, exact: true }),
  ).toBeVisible();
  const menu = page.getByRole('button', {
    name: /^(Open navigation|Abrir navegación)$/,
    exact: true,
  });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(
    page.getByText('This saved answer uses the recorded policy.', { exact: true }),
  ).toBeVisible();
  const auditStart = reads.length;
  await page.getByRole('button', { name: spanish ? 'Auditoría' : 'Audit', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('tab', { name: spanish ? 'Fuentes' : 'Sources', exact: true }).click();
  return { dialog, reads, auditStart };
}
for (const width of [1440, 390])
  for (const spanish of [false, true])
    test(`sole private receipt opens with clear source affordance ${width} ${spanish ? 'es' : 'en'}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 1000 });
      const { dialog, reads, auditStart } = await open(page, spanish);
      const row = dialog.getByRole('button', { name: /Service review notes.txt/ });
      await expect(row).toHaveAttribute('aria-pressed', 'true');
      await expect(dialog.locator('.source-detail h3')).toHaveText('Service review notes.txt');
      await expect(dialog.locator('.source-detail .technical-references')).toHaveJSProperty(
        'open',
        false,
      );
      await expect(dialog.getByText('a'.repeat(64), { exact: true })).not.toBeVisible();
      await expect(row.locator('ffk-icon[name=file] svg')).toBeVisible();
      await expect(row.locator('ffk-icon[name=chevron] svg')).toBeVisible();
      await row.focus();
      await row.press('Enter');
      await expect(row).toBeFocused();
      const geometry = await row.evaluate((node) => {
        const r = node.getBoundingClientRect(),
          style = getComputedStyle(node);
        return {
          height: r.height,
          right: r.right,
          viewport: innerWidth,
          focus: node.matches(':focus-visible'),
          outlineOffset: style.outlineOffset,
        };
      });
      expect(geometry.height).toBeGreaterThanOrEqual(44);
      expect(geometry.right).toBeLessThanOrEqual(geometry.viewport);
      expect(geometry.focus).toBe(true);
      expect(geometry.outlineOffset).toBe('-2px');
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
      const directory =
        process.env['KOINON_UI_CAPTURE_DIR'] ?? 'test-results/answer-audit-selection';
      await mkdir(directory, { recursive: true });
      await writeFile(
        resolve(directory, `sole-private-${width}-${spanish ? 'es' : 'en'}-geometry.json`),
        JSON.stringify(geometry, null, 2) + '\n',
      );
      await page.screenshot({
        path: resolve(directory, `sole-private-${width}-${spanish ? 'es' : 'en'}.png`),
        animations: 'disabled',
      });
      await row.press('Enter');
      await expect(dialog.locator('.source-detail h3')).toHaveText('Service review notes.txt');
      expect(
        reads
          .slice(auditStart)
          .some(
            (path) =>
              (path.includes('/evidence/') || path.includes('/attachments/')) &&
              !path.endsWith('/attachments/capabilities'),
          ),
      ).toBe(false);
    });
test('a sole recorded catalog passage opens without a source click', async ({ page }) => {
  const { dialog } = await open(page, false, false, true);
  await expect(dialog.locator('.source-detail blockquote')).toHaveText(
    'The recorded policy requires an annual service review.',
  );
  await expect(
    dialog.getByRole('button', { name: /Recorded operating policy.pdf/ }),
  ).toHaveAttribute('aria-pressed', 'true');
});
test('multiple catalog and private choices remain explicit and preserve keyboard selection', async ({
  page,
}) => {
  const { dialog } = await open(page, false, true);
  await expect(dialog.locator('.source-detail')).toHaveCount(0);
  const source = dialog.getByRole('button', { name: /Recorded operating policy.pdf/ });
  await source.focus();
  await page.keyboard.press('Enter');
  await expect(dialog.locator('.source-detail blockquote')).toBeVisible();
  await dialog.getByRole('button', { name: /Service review notes.txt/ }).click();
  await expect(dialog.locator('.source-detail h3')).toHaveText('Service review notes.txt');
  await expect(source).toHaveAttribute('aria-pressed', 'false');
});
