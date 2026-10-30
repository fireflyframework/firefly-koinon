// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled receipts qualify historical source navigation, not a live repository or model.
import { test, expect, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService, context } from './fixtures';

const text = 'The service review owner is Ava Chen.\nReviews take place every September.';
const sha256 = createHash('sha256').update(text).digest('hex');
const source = {
  id: 'saved-policy',
  kind: 'document',
  asset_id: 'document-one',
  source_id: 'source-one',
  title: 'Service operating policy.pdf',
  source_version_id: 'version-used',
  extraction_id: 'extraction-used',
  source_part_id: 'part-used',
  source_part_sha256: sha256,
  used_revision: 'source-part-sha256:' + sha256,
  recorded_page: 3,
  page_basis: 'recorded_loader',
  quote: text.split('\n')[0],
  availability: 'changed',
};

async function open(page: Page, spanish: boolean, mismatch = false) {
  await mockService(page, { organizationAgent: 'agent' });
  const requests: string[] = [];
  const stamp = '2026-10-30T10:00:00Z';
  const thread = {
    id: 'historical-thread',
    title: 'Service review ownership',
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
    requests.push(path);
    const json = (value: unknown) => route.fulfill({ json: value });
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
    if (path.endsWith('/chat/threads'))
      return json({ items: [thread], total: 1, page: 1, page_size: 25, pages: 1 });
    if (path.endsWith('/chat/threads/historical-thread')) return json(thread);
    if (path.endsWith('/messages'))
      return json({
        items: [
          {
            id: 'saved-answer',
            run_id: 'saved-run',
            role: 'assistant',
            status: 'completed',
            text: 'Ava Chen owns the service review.',
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
    if (path.endsWith('/chat/runs/saved-run/audit'))
      return json({
        run_id: 'saved-run',
        provenance_status: 'recorded',
        source_provenance_complete: true,
        generations: [],
        native_reads: [],
        sql_attempts: [],
        sources: [source],
        private_files: [],
      });
    if (path.endsWith('/versions/version-used/extractions/extraction-used/parts/part-used'))
      return json({
        document_id: 'document-one',
        catalog_source_id: 'source-one',
        native_source_id: 'native-source',
        source_version_id: 'version-used',
        extraction_id: 'extraction-used',
        source_part_id: 'part-used',
        kind: 'chunk',
        sha256,
        text: mismatch ? text + '\nUnrecorded replacement.' : text,
        recorded_page: 3,
        page_basis: 'recorded_loader',
        raw_sha256: 'a'.repeat(64),
        normalized_sha256: 'b'.repeat(64),
        input_sha256: 'b'.repeat(64),
      });
    return route.fallback();
  });
  await page.goto('/');
  if ((page.viewportSize()?.width ?? 1440) < 1100)
    await page
      .getByRole('button', { name: spanish ? 'Abrir navegación' : 'Open navigation', exact: true })
      .click();
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(page.getByText('Ava Chen owns the service review.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: spanish ? 'Auditoría' : 'Audit', exact: true }).click();
  const audit = page.getByRole('dialog', {
    name: spanish ? 'Auditoría de la respuesta' : 'Answer audit',
    exact: true,
  });
  await audit.getByRole('tab', { name: spanish ? 'Fuentes' : 'Sources', exact: true }).click();
  await audit
    .getByRole('button', { name: spanish ? 'Abrir fuente' : 'Open source', exact: true })
    .click();
  return requests;
}

for (const width of [1440, 390])
  for (const spanish of [false, true]) {
    test(`opens verified historical RAG source at ${width} ${spanish ? 'es' : 'en'}`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 1000 });
      const requests = await open(page, spanish);
      const panel = page.getByRole('dialog', {
        name: spanish ? 'Fuente utilizada en esta respuesta' : 'Source used in this answer',
        exact: true,
      });
      await expect(panel.locator('.recorded-content')).toHaveText(text);
      await expect(panel.locator('.source-status')).toContainText(
        spanish ? 'La fuente ha cambiado' : 'Source has changed',
      );
      await expect(panel.locator('.location')).toContainText('3');
      await panel.locator('summary').click();
      await expect(panel.getByText('version-used', { exact: true })).toBeVisible();
      await expect(panel.getByText(sha256, { exact: true })).toBeVisible();
      const geometry = await panel.evaluate((node) => ({
        width: node.getBoundingClientRect().width,
        viewport: innerWidth,
        overflow: node.scrollWidth > node.clientWidth,
        contentOverflow:
          node.querySelector('.body')!.scrollWidth > node.querySelector('.body')!.clientWidth,
        font: getComputedStyle(node).fontFamily,
      }));
      expect(geometry.width).toBeLessThanOrEqual(width);
      expect(geometry.overflow || geometry.contentOverflow).toBe(false);
      expect(geometry.font).toContain('Manrope');
      const output = process.env['KOINON_UI_CAPTURE_DIR'] ?? 'test-results/immutable-rag-source';
      await mkdir(output, { recursive: true });
      const name = `historical-source-${width}-${spanish ? 'es' : 'en'}`;
      await page.screenshot({ path: resolve(output, name + '.png'), animations: 'disabled' });
      await writeFile(
        resolve(output, name + '.json'),
        JSON.stringify({ controlled_receipts: true, ...geometry }, null, 2) + '\n',
      );
      await panel
        .getByRole('button', {
          name: spanish ? 'Volver a las fuentes' : 'Back to sources',
          exact: true,
        })
        .click();
      await expect(
        page.getByRole('dialog', {
          name: spanish ? 'Auditoría de la respuesta' : 'Answer audit',
          exact: true,
        }),
      ).toBeVisible();
      expect(requests.filter((path) => path.includes('/versions/'))).toHaveLength(1);
      expect(
        requests.some((path) => /\/documents\/document-one\/(chunks|original)$/.test(path)),
      ).toBe(false);
    });
  }

test('does not render altered historical text or navigate to a current replacement', async ({
  page,
}) => {
  const requests = await open(page, false, true);
  const panel = page.getByRole('dialog', { name: 'Source used in this answer', exact: true });
  await expect(panel.getByRole('alert')).toContainText(
    'The source does not match the recorded answer.',
  );
  await expect(panel.locator('.recorded-content')).toHaveCount(0);
  await expect(panel.getByText('Unrecorded replacement.', { exact: false })).toHaveCount(0);
  expect(requests.filter((path) => path.includes('/versions/'))).toHaveLength(1);
});
