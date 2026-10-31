// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// Controlled saved messages exercise rendering; no provider or model is invoked.
import { test, expect } from '@playwright/test';
import { mockService } from './fixtures';

for (const theme of ['light', 'dark']) {
  for (const width of [1440, 320]) {
    test(`fenced code is highlighted, safe and copyable at ${width}px in ${theme}`, async ({
      page,
      context,
    }) => {
      await page.setViewportSize({ width, height: 1100 });
      await page.addInitScript((value) => localStorage.setItem('koinon-theme', value), theme);
      await context.grantPermissions(['clipboard-read', 'clipboard-write']);
      await mockService(page, { organizationAgent: 'reader' });
      const stamp = '2026-10-31T10:00:00Z';
      const thread = {
        id: 'code-thread',
        title: 'Code review',
        title_source: 'manual',
        revision: 1,
        folder_id: null,
        archived_at: null,
        scope: {},
        created_at: stamp,
        updated_at: stamp,
      };
      const file = {
        id: 'code-file',
        filename: 'Notes.txt',
        media_type: 'text/plain',
        kind: 'document',
        size_bytes: 10,
        sha256: 'a'.repeat(64),
        status: 'ready',
        revision: 1,
        expires_at: '2099-01-01T00:00:00Z',
        available: true,
      };
      const python =
        'def greet(name):\n    return "<img src=x onerror=window.syntaxXss=1>"\n# Attachment code-file: Notes.txt\n';
      const php = '<?php\nfunction greet($name) { return "Hello, " . $name; }\n';
      const sql = 'SELECT "name", 42 FROM "source";\n';
      const unknown = '<svg onload="window.syntaxXss=1">literal &amp; text</svg>\n';
      const text =
        'Source: Attachment code-file: Notes.txt\n```python\n' +
        python +
        '```\n~~~php\n' +
        php +
        '~~~\n```sql\n' +
        sql +
        '```\n```unrecognized\n' +
        unknown +
        '```';
      let modelRequests = 0;
      await page.route('**/bff/api/v1/tenants/*/**', async (route) => {
        const path = new URL(route.request().url()).pathname;
        const json = (value: unknown) => route.fulfill({ json: value });
        if (path.endsWith('/chat/threads'))
          return json({ items: [thread], total: 1, page: 1, page_size: 25, pages: 1 });
        if (path.endsWith('/chat/threads/code-thread')) return json(thread);
        if (path.endsWith('/messages'))
          return json({
            items: [
              {
                id: 'user-code',
                role: 'user',
                text: 'Review these code examples.',
                status: 'completed',
                attachments: [file],
                citations: [],
                artifacts: [],
                created_at: stamp,
              },
              {
                id: 'assistant-code',
                role: 'assistant',
                text,
                status: 'completed',
                citations: [],
                artifacts: [],
                created_at: stamp,
              },
            ],
            next_cursor: null,
          });
        if (path.endsWith('/agents'))
          return json({
            items: [{ id: 'reader', name: 'Knowledge guide', status: 'ready', checks: [] }],
          });
        if (path.endsWith('/attachments/capabilities'))
          return json({
            storage: { available: true, reason: '' },
            database: { available: true, reason: '' },
            extraction: { available: true, reason: '' },
            formats: [],
            promotion: {},
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
          });
        if (path.endsWith('/attachments')) return json({ items: [] });
        if (path.endsWith('/runs') && route.request().method() === 'POST') ++modelRequests;
        return route.fallback();
      });
      await page.goto('/');
      if (width === 320)
        await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
      await page.getByRole('button', { name: 'Chat', exact: true }).click();
      const message = page.locator('.assistant-message .message-text');
      const blocks = message.locator('ffk-code-block');
      await expect(blocks).toHaveCount(4);
      await expect(blocks.nth(0).locator('.hljs-keyword').first()).toHaveText('def');
      await expect(blocks.nth(1).locator('.hljs-keyword').first()).toHaveText('function');
      await expect(blocks.nth(2).locator('.keyword').first()).toHaveText('SELECT');
      await expect(blocks.nth(3).locator('pre')).toHaveText(unknown);
      expect(await blocks.nth(3).locator('pre').textContent()).toBe(unknown);
      await expect(message.locator('button[title="Download source file"]')).toHaveCount(1);
      await expect(message.locator('pre img, pre svg, pre script')).toHaveCount(0);
      expect(await page.evaluate(() => 'syntaxXss' in window)).toBe(false);
      for (const [index, code] of [python, php, sql, unknown].entries()) {
        expect(await blocks.nth(index).locator('pre').textContent()).toBe(code);
        await blocks
          .nth(index)
          .getByRole('button', { name: index === 2 ? 'Copy SQL' : 'Copy code', exact: true })
          .click();
        expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(code);
      }
      const pre = blocks.first().locator('pre');
      const dimensions = await pre.evaluate((element) => ({
        client: element.clientWidth,
        scroll: element.scrollWidth,
        whitespace: getComputedStyle(element).whiteSpace,
      }));
      expect(dimensions.whitespace).toBe('pre');
      if (width === 320) expect(dimensions.scroll).toBeGreaterThan(dimensions.client);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
        width,
      );
      expect(modelRequests).toBe(0);
      await message.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `test-results/code-${theme}-${width}.png`, fullPage: true });
    });
  }
}
