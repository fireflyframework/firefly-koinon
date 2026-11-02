// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import { mockService } from './fixtures';
// The native PDF handoff requires full Chromium, which the hosted browser lane installs.
test.use({ channel: 'chromium' });
const text =
  'Service ownership and review\n\nThe documented review owner is Ava Chen.\n\n<script>Source text is displayed safely, never executed.</script>\n\nLa revisión mantiene la evidencia original.';
const hash = createHash('sha256').update(text).digest('hex');
function pdfFixture() {
  const content = 'BT /F1 18 Tf 40 220 Td (Controlled document preview) Tj ET';
  const objects = [
    '<</Type/Catalog/Pages 2 0 R>>',
    '<</Type/Pages/Kids[3 0 R]/Count 1>>',
    '<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 300]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>',
    '<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>',
    `<</Length ${content.length}>>\nstream\n${content}\nendstream`,
  ];
  let body = '%PDF-1.4\n';
  const offsets = [0];
  for (const [index, value] of objects.entries()) {
    offsets.push(Buffer.byteLength(body));
    body += `${index + 1} 0 obj\n${value}\nendobj\n`;
  }
  const xref = Buffer.byteLength(body);
  body +=
    'xref\n0 6\n0000000000 65535 f \n' +
    offsets
      .slice(1)
      .map((offset) => String(offset).padStart(10, '0') + ' 00000 n \n')
      .join('') +
    `trailer\n<</Size 6/Root 1 0 R>>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body);
}

async function fixture(
  page: Page,
  options: { pending?: boolean; denied?: boolean; image?: boolean } = {},
) {
  await mockService(page);
  let originals = 0;
  let denied = !!options.denied;
  const media = options.image ? 'image/png' : 'application/pdf';
  const original = options.image
    ? Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j0d8AAAAASUVORK5CYII=',
        'base64',
      )
    : pdfFixture();
  const originalHash = createHash('sha256').update(original).digest('hex');
  await page.route('**/bff/api/v1/**', async (route) => {
    const req = route.request(),
      path = new URL(req.url()).pathname.replace('/bff/api/v1', '');
    if (path.endsWith('/catalog/availability'))
      return route.fulfill({
        json: {
          observed_at: '2026-11-02T00:00:00Z',
          items: {
            'document-one': {
              phase: 'failed',
              read: { state: options.pending ? 'pending' : 'ready' },
              revision: { source_version_id: 'serving-old', extraction_id: 'view-old' },
            },
          },
        },
      });
    if (!path.includes('/documents/')) return route.fallback();
    if (denied)
      return route.fulfill({
        status: 403,
        json: { code: 'ACCESS_DENIED', detail: 'Private error should not be rendered' },
      });
    if (path.endsWith('/original')) {
      originals++;
      return route.fulfill({
        contentType: 'application/octet-stream',
        headers: {
          'Content-Disposition': 'attachment; filename="Service policy.pdf"',
          ETag: '"' + originalHash + '"',
        },
        body: original,
      });
    }
    const identity = {
      document_id: 'document-one',
      catalog_source_id: 'source-one',
      native_source_id: 'native-source',
      source_version_id: 'serving-old',
      extraction_id: 'view-old',
    };
    if (path.endsWith('/parts/part-one'))
      return route.fulfill({
        json: {
          ...identity,
          source_part_id: 'part-one',
          kind: 'chunk',
          sha256: hash,
          text,
          recorded_page: 2,
          page_basis: 'recorded_loader',
        },
      });
    if (path.endsWith('/parts'))
      return route.fulfill({
        json: {
          items: [
            {
              ...identity,
              source_part_id: 'part-one',
              kind: 'chunk',
              ordinal: 0,
              sha256: hash,
              recorded_page: 2,
            },
          ],
          total: 1,
          page: 1,
          page_size: 25,
          pages: 1,
        },
      });
    if (path.endsWith('/versions/serving-old'))
      return route.fulfill({
        json: {
          ...identity,
          filename: 'Service policy.pdf',
          media_type: media,
          byte_size: original.byteLength,
          sha256: originalHash,
          created_at: '2026-11-01T09:00:00Z',
        },
      });
    throw Error('Unpinned document read: ' + path);
  });
  await page.goto('/library');
  for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
    await page.getByRole('button', { name, exact: true }).click();
  return {
    originals: () => originals,
    revoke: () => {
      denied = true;
    },
  };
}
for (const width of [1440, 390])
  test(`document reader ${width} keeps original pins, keyboard focus and safe readable layout`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const service = await fixture(page);
    const trigger = page.getByRole('button', { name: 'Service operating policy.pdf', exact: true });
    await trigger.focus();
    await page.keyboard.press('Enter');
    const panel = page.getByRole('dialog', { name: 'Service operating policy.pdf', exact: true });
    await expect(panel).toBeVisible();
    await expect(panel.locator('.document-text')).toContainText(text);
    await expect(panel.locator('.document-text script')).toHaveCount(0);
    expect(service.originals()).toBe(0);
    await expect(
      panel.getByText('This is extracted text, not the original page layout.'),
    ).toBeVisible();
    await panel.getByText('Document version', { exact: true }).first().click();
    await expect(panel.getByText('serving-old', { exact: true })).toBeVisible();
    expect(await panel.evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
    const downloadPromise = page.waitForEvent('download');
    await panel.getByRole('button', { name: 'Download original', exact: true }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe('Service policy.pdf');
    expect(service.originals()).toBe(1);
    const dir = process.env['KOINON_VIEWER_SCREENSHOTS'];
    if (dir) {
      await mkdir(dir, { recursive: true });
      await page.screenshot({ path: `${dir}/reader-${width}.png` });
    }
    await page.keyboard.press('Escape');
    await expect(panel).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });
for (const width of [1440, 390])
  test(`document context action opens the same authorized reader at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const service = await fixture(page);
    const trigger = page.getByRole('button', {
      name: 'Actions for Service operating policy.pdf',
      exact: true,
    });
    if (width === 1440) {
      await trigger.focus();
      await page.keyboard.press('Shift+F10');
    } else await trigger.click();
    const menu = page.getByRole('menu', { name: 'Library actions', exact: true });
    const read = menu.getByRole('menuitem', { name: 'Read document', exact: true });
    await expect(read).toBeFocused();
    const dir = process.env['KOINON_LIBRARY_STATE_SCREENSHOTS'];
    if (dir) {
      await mkdir(dir, { recursive: true });
      await page.screenshot({
        path: `${dir}/document-context-${width}.png`,
        animations: 'disabled',
      });
    }
    if (width === 1440) await page.keyboard.press('Enter');
    else await read.click();
    const panel = page.getByRole('dialog', { name: 'Service operating policy.pdf', exact: true });
    await expect(panel.locator('.document-text')).toContainText(text);
    expect(service.originals()).toBe(0);
    await page.keyboard.press('Escape');
    await expect(panel).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

test('pending source offers truthful read status and no original request', async ({ page }) => {
  const service = await fixture(page, { pending: true });
  await page.getByRole('button', { name: 'Service operating policy.pdf', exact: true }).click();
  const panel = page.getByRole('dialog', { name: 'Service operating policy.pdf', exact: true });
  await expect(panel.getByRole('alert')).toContainText('not yet available');
  await expect(
    panel.getByRole('button', { name: 'Download original', exact: true }),
  ).toBeDisabled();
  expect(service.originals()).toBe(0);
});
test('permissions denial clears content and never exposes private backend error', async ({
  page,
}) => {
  await fixture(page, { denied: true });
  await page.getByRole('button', { name: 'Service operating policy.pdf', exact: true }).click();
  const panel = page.getByRole('dialog', { name: 'Service operating policy.pdf', exact: true });
  await expect(panel.getByRole('alert')).toContainText('Your current access');
  await expect(panel).not.toContainText('Private error');
  await expect(
    panel.getByRole('button', { name: 'Download original', exact: true }),
  ).toBeDisabled();
});
test('explicit image preview uses local Blob URL and a supported image MIME', async ({ page }) => {
  const service = await fixture(page, { image: true });
  await page.getByRole('button', { name: 'Service operating policy.pdf', exact: true }).click();
  const panel = page.getByRole('dialog', { name: 'Service operating policy.pdf', exact: true });
  await expect(panel.locator('.document-text')).toContainText(text);
  await panel.getByRole('button', { name: 'Preview original', exact: true }).click();
  const image = panel.locator('.original img');
  await expect(image).toBeVisible();
  await expect(image).toHaveAttribute('src', /^blob:/);
  expect(service.originals()).toBe(1);
  expect(await image.evaluate((e) => (e as HTMLImageElement).naturalWidth)).toBe(1);
});

test.describe('native PDF browser handoff', () => {
  test('PDF octet-stream original opens in an isolated browser tab and remains downloadable', async ({
    page,
  }) => {
    const service = await fixture(page);
    await page.getByRole('button', { name: 'Service operating policy.pdf', exact: true }).click();
    const panel = page.getByRole('dialog', { name: 'Service operating policy.pdf', exact: true });
    await expect(panel.locator('.document-text')).toContainText(text);
    await panel.getByRole('button', { name: 'Prepare PDF', exact: true }).click();
    const link = panel.getByRole('link', { name: 'Open PDF in browser tab', exact: true });
    await expect(link).toHaveAttribute('href', /^blob:/);
    await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    await expect(panel.locator('iframe')).toHaveCount(0);
    const preparedUrl = await link.getAttribute('href');
    const downloadPromise = page.waitForEvent('download');
    await panel.getByRole('button', { name: 'Download original', exact: true }).click();
    expect((await downloadPromise).suggestedFilename()).toBe('Service policy.pdf');
    expect(service.originals()).toBe(2);
    await expect(link).toHaveAttribute('href', preparedUrl!);
    const opened = page.waitForEvent('popup');
    await link.click();
    const pdf = await opened;
    await expect(pdf).toHaveURL(/^blob:/);
    expect(await pdf.evaluate(() => window.opener === null)).toBe(true);
    const screenshots = process.env['KOINON_VIEWER_SCREENSHOTS'];
    if (screenshots) {
      await pdf.waitForTimeout(1000);
      await pdf.screenshot({ path: `${screenshots}/pdf-native-browser-tab.png` });
    }
    await pdf.close();
    expect(service.originals()).toBe(2);
    const dir = process.env['KOINON_VIEWER_SCREENSHOTS'];
    if (dir) await page.screenshot({ path: `${dir}/reader-pdf.png` });
  });
});
test('revoked access clears already displayed text before another original can be released', async ({
  page,
}) => {
  const service = await fixture(page);
  await page.getByRole('button', { name: 'Service operating policy.pdf', exact: true }).click();
  const panel = page.getByRole('dialog', { name: 'Service operating policy.pdf', exact: true });
  await expect(panel.locator('.document-text')).toContainText(text);
  service.revoke();
  await panel.getByRole('button', { name: 'Download original', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('Your current access');
  await expect(panel.locator('.document-text')).toHaveCount(0);
  await expect(
    panel.getByRole('button', { name: 'Download original', exact: true }),
  ).toBeDisabled();
  expect(service.originals()).toBe(0);
});
test('document reading keeps the separate Library inspector accessible', async ({ page }) => {
  await fixture(page);
  await page.getByRole('button', { name: 'Service operating policy.pdf', exact: true }).click();
  const panel = page.getByRole('dialog', { name: 'Service operating policy.pdf', exact: true });
  await expect(panel.locator('.document-text')).toContainText(text);
  await page.keyboard.press('Escape');
  await page
    .getByRole('button', { name: 'Details for Service operating policy.pdf', exact: true })
    .click();
  await expect(page.getByLabel('Resource details', { exact: true })).toBeVisible();
});

test('mobile reader labels and safe source details are available in Spanish', async ({ page }) => {
  await fixture(page);
  await page.route('**/bff/api/v1/profile', (route) =>
    route.fulfill({
      json: {
        subject: 'synthetic.reviewer',
        display_name: 'Alex Rivera',
        locale: 'es-ES',
        time_zone: 'UTC',
        response_language: 'es',
        avatar_url: null,
        avatar_version: null,
      },
    }),
  );
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto('/library');
  for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
    await page.getByRole('button', { name, exact: true }).click();
  await page.getByRole('button', { name: 'Service operating policy.pdf', exact: true }).click();
  const panel = page.getByRole('dialog', { name: 'Service operating policy.pdf', exact: true });
  await expect(panel.locator('.document-text')).toContainText(text);
  await expect(
    panel.getByRole('button', { name: 'Descargar original', exact: true }),
  ).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Preparar PDF', exact: true })).toBeVisible();
  await expect(panel).toContainText('no el diseño de página original');
  const dir = process.env['KOINON_VIEWER_SCREENSHOTS'];
  if (dir) await page.screenshot({ path: `${dir}/reader-390-spanish.png` });
});

test('separate document details still support the normal reviewed metadata editor', async ({
  page,
}) => {
  await fixture(page);
  await page
    .getByRole('button', { name: 'Details for Service operating policy.pdf', exact: true })
    .click();
  await page
    .getByLabel('Resource details', { exact: true })
    .getByRole('button', { name: 'Edit details', exact: true })
    .click();
  const dialog = page.getByRole('dialog', { name: 'Edit details', exact: true });
  await dialog
    .getByRole('textbox', { name: 'Name', exact: true })
    .fill('Reviewed operating policy.pdf');
  await dialog.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Reviewed operating policy.pdf', exact: true }),
  ).toBeVisible();
});
