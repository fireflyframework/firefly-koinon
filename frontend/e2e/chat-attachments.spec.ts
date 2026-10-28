// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled HTTP fixtures verify the UI contract; native parsing is qualified separately.
import { test, expect } from '@playwright/test';
import { mockService } from './fixtures';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
const capabilities = {
  storage: { available: true, reason: 'Fixture' },
  database: { available: true, reason: 'Fixture' },
  extraction: { available: true, reason: 'Fixture' },
  formats: [
    {
      kind: 'document',
      media_type: 'text/plain',
      extensions: ['.txt'],
      extraction: { available: true, reason: 'Fixture' },
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
};
test('uploads a private file, waits for extraction and submits only selected IDs', async ({
  page,
}) => {
  await mockService(page);
  let uploaded = false,
    reads = 0,
    submitted = false;
  const runBodies: unknown[] = [];
  const thread = {
    id: 'files-thread',
    title: 'File review',
    revision: 1,
    title_source: 'manual',
    folder_id: null,
    archived_at: null,
    scope: {},
    created_at: '2026-10-26T10:00:00Z',
    updated_at: '2026-10-26T10:00:00Z',
  };
  const file = (ready: boolean) => ({
    id: 'private-file',
    tenant_id: 'fixture-org',
    thread_id: thread.id,
    filename: 'Notes.txt',
    media_type: 'text/plain',
    kind: 'document',
    size_bytes: 19,
    sha256: 'a'.repeat(64),
    status: ready ? 'ready' : 'queued',
    revision: ready ? 2 : 1,
    created_at: thread.created_at,
    expires_at: '2099-01-01T00:00:00Z',
    chunk_count: ready ? 1 : 0,
    progress: { status: ready ? 'succeeded' : 'queued', percent: ready ? 100 : 0, attempts: 1 },
  });
  const activity = {
    call_id: 'private-read',
    tool_name: 'search_private_attachments',
    status: 'completed',
    occurred_at: thread.created_at,
    summary: 'Read the selected private file.',
    result_id: 'private-result',
  };
  await page.route('**/bff/api/v1/**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    const json = (value: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
    if (path.endsWith('/capabilities'))
      return json(
        path.includes('/attachments/')
          ? capabilities
          : { providers: [], features: [], attachments: capabilities },
      );
    if (path.endsWith('/agents'))
      return json({
        items: [
          { id: 'reader', name: 'koinon', input_modalities: ['text'], status: 'ready', checks: [] },
        ],
      });
    if (path.endsWith('/chat/folders'))
      return json({ items: [], page: 1, page_size: 25, total: 0, pages: 0 });
    if (path.endsWith('/chat/threads'))
      return request.method() === 'POST'
        ? json(thread)
        : json({
            items: uploaded ? [thread] : [],
            page: 1,
            page_size: 25,
            total: uploaded ? 1 : 0,
            pages: uploaded ? 1 : 0,
          });
    if (path.endsWith('/chat/threads/files-thread')) return json(thread);
    if (path.endsWith('/attachments') && request.method() === 'POST') {
      expect(request.headers()['x-xsrf-token']).toBe('synthetic-csrf+token');
      expect(request.headers()['idempotency-key']).toBeTruthy();
      expect(request.postDataBuffer()?.toString()).toContain('Notes.txt');
      uploaded = true;
      return json(file(false), 202);
    }
    if (path.endsWith('/attachments/private-file')) {
      ++reads;
      return json(file(reads > 1));
    }
    if (path.endsWith('/messages'))
      return json({
        items: submitted
          ? [
              {
                id: 'user-file-message',
                role: 'user',
                text: 'Summarize these notes.',
                status: 'completed',
                attachments: [{ ...file(true), available: true }],
                citations: [],
                artifacts: [],
                created_at: thread.created_at,
              },
              {
                id: 'answer',
                role: 'assistant',
                run_id: 'file-run',
                text: 'The notes describe the service review. Source: Attachment private-file: Notes.txt.',
                status: 'completed',
                citations: [],
                tool_activities: [activity],
                tool_activity_count: 1,
                tool_activity_has_more: false,
                artifacts: [
                  {
                    id: 'private-evidence',
                    kind: 'openui',
                    run_id: 'file-run',
                    language:
                      'root = KnowledgeAnswer([item])\nitem = Evidence("private-result", "auto")',
                    complete: true,
                  },
                  {
                    id: 'private-evidence-repeat',
                    kind: 'openui',
                    run_id: 'file-run',
                    language:
                      'root = KnowledgeAnswer([item])\nitem = Evidence("private-result-repeat", "auto")',
                    complete: true,
                  },
                ],
                created_at: thread.created_at,
              },
            ]
          : [],
        next_cursor: null,
      });
    if (path.endsWith('/chat/runs/file-run/audit'))
      return json({
        run_id: 'file-run',
        provenance_status: 'recorded',
        source_provenance_complete: true,
        generations: [],
        sources: [],
        private_files: [{ ...file(true), used_revision: 2, availability: 'available' }],
        native_reads: [],
        sql_attempts: [],
      });
    if (path.endsWith('/chat/runs/file-run/activity'))
      return json({ items: [activity], page: 1, page_size: 25, total: 1, pages: 1 });
    if (path.endsWith('/results/private-result') || path.endsWith('/results/private-result-repeat'))
      return json({
        id: path.split('/').pop(),
        run_id: 'file-run',
        kind: 'attachment',
        data: {
          attachments: [
            {
              id: 'private-file',
              filename: 'Notes.txt',
              media_type: 'text/plain',
              sha256: 'a'.repeat(64),
              revision: 2,
              complete: true,
              chunk_ids: ['chunk'],
              total_chunks: 1,
              warnings: [],
            },
          ],
        },
      });
    if (path.endsWith('/runs')) {
      submitted = true;
      runBodies.push(request.postDataJSON());
      return json({ run_id: 'file-run', message_id: 'answer' });
    }
    return route.fallback();
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  const composer = page.locator('ffk-chat-composer');
  await composer.getByRole('button', { name: 'Add context', exact: true }).click();
  await expect(page.getByRole('menuitem', { name: /Attach files/ })).toBeEnabled();
  await page.keyboard.press('Escape');
  await composer.locator('input[type=file]').setInputFiles({
    name: 'Notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Service review notes'),
  });
  await composer
    .getByRole('textbox', { name: 'Message koinon', exact: true })
    .fill('Summarize these notes.');
  await expect(composer.getByText('Reading file', { exact: true })).toBeVisible();
  await expect(composer.getByRole('button', { name: 'Send', exact: true })).toBeDisabled();
  await expect(composer.getByText('Ready', { exact: true })).toBeVisible({ timeout: 10000 });
  await composer.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(page.locator('.assistant-message .message-text')).toHaveText(
    'The notes describe the service review. Source: Notes.txt.',
  );
  await expect(
    page
      .locator('.assistant-message .message-text')
      .getByRole('button', { name: 'Notes.txt', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Attached files used', exact: true })).toHaveCount(
    0,
  );
  await expect(page.getByRole('region', { name: 'Supporting evidence', exact: true })).toHaveCount(
    0,
  );
  await page.getByRole('button', { name: 'Audit', exact: true }).click();
  const audit = page.getByRole('dialog', { name: 'Answer audit', exact: true });
  await audit.getByRole('tab', { name: 'Sources', exact: true }).click();
  await audit.getByRole('button', { name: /Notes.txt/ }).click();
  const technical = audit.locator('.source-detail .technical-references');
  await expect(technical).toHaveJSProperty('open', false);
  await expect(audit.getByText('a'.repeat(64), { exact: true })).not.toBeVisible();
  await technical.locator('summary').click();
  await expect(audit.getByText('a'.repeat(64), { exact: true })).toBeVisible();
  await audit.getByRole('tab', { name: 'Execution', exact: true }).click();
  await audit.getByRole('button', { name: 'View result', exact: true }).click();
  await expect(
    audit.getByRole('heading', { name: 'Attached files used', exact: true }),
  ).toBeVisible();
  await expect(page.locator('.artifact-error,.evidence-error')).toHaveCount(0);
  expect(runBodies).toHaveLength(1);
  expect(runBodies[0]).toMatchObject({ attachment_ids: ['private-file'] });
  await page.keyboard.press('Escape');
  await expect(composer.getByRole('listitem')).toHaveCount(0);
});

for (const spanish of [false, true])
  test(`configured unverified storage permits an honest first upload choice ${spanish ? 'Spanish' : 'English'}`, async ({
    page,
  }) => {
    await mockService(page);
    const pending = {
      ...capabilities,
      storage: {
        available: null,
        configured: true,
        reason: 'Configured; no availability observation',
      },
    };
    await page.route('**/bff/api/v1/**', async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/capabilities'))
        return route.fulfill({
          json: path.includes('/attachments/')
            ? pending
            : { providers: [], features: [], attachments: pending },
        });
      if (path.endsWith('/agents'))
        return route.fulfill({
          json: {
            items: [
              {
                id: 'reader',
                name: 'Reader',
                input_modalities: ['text'],
                status: 'ready',
                checks: [],
              },
            ],
          },
        });
      if (path.endsWith('/chat/threads') || path.endsWith('/chat/folders'))
        return route.fulfill({ json: { items: [], page: 1, pages: 0, total: 0 } });
      if (spanish && path.endsWith('/profile'))
        return route.fulfill({
          json: {
            subject: 'synthetic.reviewer',
            display_name: 'Alex Rivera',
            locale: 'es-ES',
            time_zone: 'UTC',
            response_language: 'en',
            avatar_version: null,
          },
        });
      return route.fallback();
    });
    await page.goto('/');
    if (spanish)
      await expect(page.getByRole('heading', { name: 'Biblioteca', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Chat', exact: true }).click();
    const composer = page.locator('ffk-chat-composer');
    await expect(composer.locator('textarea')).toBeEnabled();
    await expect(composer.locator('.composer-hint')).toHaveText(
      spanish
        ? 'El almacenamiento privado de archivos está configurado, pero aún no se ha verificado. Tu carga comprobará su disponibilidad.'
        : 'Private file storage is configured but has not been verified. Your upload will check availability.',
    );
    await composer
      .getByRole('button', { name: spanish ? 'Añadir contexto' : 'Add context', exact: true })
      .click();
    await expect(
      page.getByRole('menuitem', { name: spanish ? /Adjuntar archivos/ : /Attach files/ }),
    ).toBeEnabled();
    await expect(composer.locator('input[type=file]')).toBeEnabled();
    const directory = resolve('../../control/frontend-captures/bundle-v19');
    await mkdir(directory, { recursive: true });
    await page.screenshot({
      path: resolve(directory, `storage-unverified-${spanish ? 'es' : 'en'}.png`),
      fullPage: true,
    });
  });
