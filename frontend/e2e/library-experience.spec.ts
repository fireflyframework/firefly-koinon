// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { expect, test, type Page } from '@playwright/test';
import type { CatalogSummary } from '@fireflyframework/koinon-sdk';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { entry, mockService } from './fixtures';
const directory = resolve('../../control/frontend-captures/library-experience');
const summary = (values: Partial<CatalogSummary> = {}): CatalogSummary => ({
  child_count: null,
  document_count: null,
  dataset_count: null,
  table_count: null,
  row_count: null,
  column_count: null,
  page_count: null,
  size_bytes: null,
  format: null,
  language: null,
  tags: [],
  ...values,
});
async function setup(page: Page) {
  const summaries: Record<string, CatalogSummary> = {
    'workspace-one': summary({ child_count: 1 }),
    'project-one': summary({ child_count: 1 }),
    'collection-one': summary({
      child_count: 32,
      document_count: 16,
      dataset_count: 16,
      tags: ['operations'],
    }),
    'document-one': summary({
      page_count: 12,
      size_bytes: 286720,
      format: 'pdf',
      language: 'en',
      tags: ['pdf', 'en', 'policy'],
    }),
    'dataset-one': summary({
      table_count: 3,
      row_count: 42150,
      column_count: 18,
      size_bytes: 2457600,
      format: 'csv',
      tags: ['csv', 'operations'],
    }),
  };
  const service = await mockService(page, {
    summaries,
    actors: {
      'synthetic.reviewer': {
        subject: 'synthetic.reviewer',
        display_name: 'Alex Rivera',
        avatar_data_url: null,
        avatar_version: null,
      },
    },
  });
  service.rows.find((row) => row.id === 'document-one')!.updated_by = 'synthetic.reviewer';
  service.rows.find((row) => row.id === 'dataset-one')!.updated_by = 'synthetic.reviewer';
  for (let i = 0; i < 30; i++) {
    const id = 'additional-' + i;
    summaries[id] = summary(
      i % 2
        ? { page_count: 4, format: 'pdf', tags: ['pdf', 'policy'] }
        : { table_count: 1, row_count: 1500, format: 'csv', tags: ['csv', 'operations'] },
    );
    service.rows.push(
      entry(
        id,
        i % 2 ? 'document' : 'dataset',
        (i % 2 ? 'Supplementary operating guide ' : 'Supplementary service records ') +
          String(i).padStart(2, '0'),
        'source-one',
        { metadata: { format: i % 2 ? 'pdf' : 'csv', tags: [i % 2 ? 'policy' : 'operations'] } },
      ),
    );
  }
  await page.goto('/');
  return service;
}
async function openLibrary(page: Page) {
  for (const name of ['Research operations', 'Operations intelligence', 'Reference library'])
    await page.getByRole('button', { name, exact: true }).click();
}
async function capture(page: Page, name: string) {
  await mkdir(directory, { recursive: true });
  await page.evaluate(() => {
    document
      .querySelector<HTMLElement>('ffk-workbench')
      ?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 22px)');
    document.getElementById('controlled-review-label')?.remove();
    const mark = document.createElement('div');
    mark.id = 'controlled-review-label';
    mark.textContent = 'Controlled metadata fixtures · Frontend review only';
    mark.style.cssText =
      'position:fixed;bottom:0;left:0;right:0;z-index:9999;padding:5px 12px;background:#855414;color:white;font:10px system-ui;text-align:center;pointer-events:none';
    document.body.append(mark);
  });
  await page.screenshot({
    path: resolve(directory, name + '.png'),
    fullPage: true,
    animations: 'disabled',
  });
}
for (const width of [1440, 1024, 390])
  test(`library columns and pagination remain readable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await setup(page);
    if (width === 1440) {
      await page.getByRole('button', { name: 'Research operations', exact: true }).click();
      await page.getByRole('button', { name: 'Operations intelligence', exact: true }).click();
      await capture(page, 'folders-1440');
      await page.getByRole('button', { name: 'Library', exact: true }).first().click();
    }
    await openLibrary(page);
    await expect(page.locator('ffk-workbench')).toHaveAttribute('style', /--ffk-font/);
    await page.evaluate(() => document.fonts.ready);
    if (width === 390) {
      const heading = await page.locator('.library-heading').boundingBox();
      const title = await page
        .getByRole('heading', { name: 'Reference library', exact: true })
        .boundingBox();
      const add = await page
        .getByRole('button', { name: 'Add knowledge', exact: true })
        .boundingBox();
      expect(heading!.height).toBeLessThanOrEqual(88);
      expect(Math.abs(title!.y - add!.y)).toBeLessThan(8);
      await expect(page.locator('.library-heading p.generic-description')).not.toBeVisible();
    }
    await expect(page.getByRole('button', { name: 'PDF', exact: true }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'English', exact: true })).toBeVisible();
    const nav = page.getByRole('navigation', { name: 'Library pagination' });
    await expect(nav.getByRole('combobox', { name: 'Library Items per page' })).toBeVisible();
    await expect(nav.getByText('Per page', { exact: false })).toBeVisible();
    const label = nav.locator('label');
    expect(
      await label.evaluate((el) => {
        const style = getComputedStyle(el);
        return style.whiteSpace === 'nowrap' && el.scrollWidth <= el.clientWidth;
      }),
    ).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await expect(
      page
        .locator('.contents:visible, .mobile-contents:visible')
        .filter({ hasText: '42,150 rows' }),
    ).toBeVisible();
    await expect(
      page.locator('button.tag:visible').filter({ hasText: 'operations' }).first(),
    ).toBeVisible();
    await capture(page, 'library-' + width);
    await nav.scrollIntoViewIfNeeded();
    await capture(page, 'pagination-' + width);
    await page.locator('summary').filter({ hasText: 'More filters' }).click();
    const filterForm = page.locator('.filter-options form');
    await filterForm.scrollIntoViewIfNeeded();
    const filterBounds = await filterForm.boundingBox();
    expect(filterBounds!.x).toBeGreaterThanOrEqual(0);
    expect(filterBounds!.x + filterBounds!.width).toBeLessThanOrEqual(width);
    if (width === 1440) {
      const triggerBounds = await page
        .locator('summary')
        .filter({ hasText: 'More filters' })
        .boundingBox();
      expect(Math.abs(filterBounds!.x - triggerBounds!.x)).toBeLessThan(2);
    }
    await capture(page, 'filters-' + width);
  });
test('header sorting and metadata filters query the whole collection and reset pagination', async ({
  page,
}) => {
  const service = await setup(page);
  await openLibrary(page);
  await page.getByRole('button', { name: 'Next library page', exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'Library pagination' })).toContainText(
    'Page 2 of 2',
  );
  await page.getByRole('columnheader', { name: 'Name' }).getByRole('button').click();
  await expect
    .poll(() => service.reads.filter((read) => read.query['view'] === 'library').at(-1)?.query)
    .toMatchObject({ sort: 'name', order: 'desc', page: '1' });
  await page.locator('button.tag:visible').filter({ hasText: 'operations' }).first().click();
  await expect
    .poll(() => service.reads.filter((read) => read.query['view'] === 'library').at(-1)?.query)
    .toMatchObject({ tag: 'operations', page: '1' });
  await expect(page.getByRole('button', { name: 'Clear filters', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
  await page.locator('summary').filter({ hasText: 'More filters' }).click();
  await page.getByRole('textbox', { name: 'Format', exact: true }).fill('PDF');
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
  await expect
    .poll(() => service.reads.filter((read) => read.query['view'] === 'library').at(-1)?.query)
    .toMatchObject({ format: 'pdf', page: '1' });
  await page.locator('.filter-options select[name="sort"]').selectOption('created_at.desc');
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
  await expect
    .poll(() => service.reads.filter((read) => read.query['view'] === 'library').at(-1)?.query)
    .toMatchObject({ sort: 'created_at', order: 'desc', format: 'pdf', page: '1' });
  expect(service.writes).toEqual([]);
});
for (const width of [320, 390])
  test(`Spanish pagination wraps complete groups at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 960 });
    await setup(page);
    await page.route('**/bff/api/v1/profile', (route) =>
      route.fulfill({
        json: {
          subject: 'synthetic.reviewer',
          display_name: 'Alex Rivera',
          locale: 'es-MX',
          time_zone: 'UTC',
          response_language: 'es',
          avatar_url: null,
          avatar_version: null,
        },
      }),
    );
    await page.reload();
    await openLibrary(page);
    const nav = page.locator('ffk-pagination nav');
    await nav.scrollIntoViewIfNeeded();
    await expect(nav.getByRole('combobox')).toBeVisible();
    const geometry = await nav.evaluate((element) => {
      const label = element.querySelector('label')!;
      const navigation = element.querySelector('.page-navigation')!;
      const labelBox = label.getBoundingClientRect();
      const navBox = navigation.getBoundingClientRect();
      const outerBox = element.getBoundingClientRect();
      return {
        nowrap: getComputedStyle(label).whiteSpace,
        width: label.scrollWidth,
        client: label.clientWidth,
        inside:
          labelBox.left >= outerBox.left &&
          labelBox.right <= outerBox.right &&
          navBox.right <= outerBox.right,
        labelAbove: labelBox.bottom <= navBox.top,
      };
    });
    expect(geometry.nowrap).toBe('nowrap');
    expect(geometry.width).toBeLessThanOrEqual(geometry.client);
    expect(geometry.inside).toBe(true);
    expect(geometry.labelAbove).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await capture(page, 'pagination-es-' + width);
  });
