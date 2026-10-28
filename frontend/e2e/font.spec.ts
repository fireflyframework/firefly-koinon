// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { mockService } from './fixtures';
for (const host of ['consumer', 'elements'])
  test(`clean ${host} host loads and uses canonical Manrope font bytes`, async ({ page }) => {
    const received: Promise<string>[] = [];
    page.on('response', (response) => {
      if (/manrope.*\.woff2/i.test(response.url()))
        received.push(
          response.body().then((body) => createHash('sha256').update(body).digest('hex')),
        );
    });
    await mockService(page);
    await page.goto('/' + host + '/');
    if (host === 'elements') {
      await page.waitForFunction(() => !!customElements.get('firefly-koinon'));
      await page.evaluate(async () => {
        const sdk = await import('/sdk/index.js');
        const element = document.querySelector('firefly-koinon') as HTMLElement & {
          client: unknown;
          tenantId: string;
          showNavigation: boolean;
        };
        element.tenantId = 'tenant-one';
        element.showNavigation = false;
        element.client = new sdk.KoinonClient({
          transport: new sdk.FetchTransport({ baseUrl: '/bff/api/v1' }),
        });
      });
    }
    await expect(
      page
        .getByRole('button', { name: 'Research operations', exact: true })
        .or(page.getByRole('button', { name: 'Reference library', exact: true }))
        .first(),
    ).toBeVisible();
    await expect
      .poll(() =>
        page.evaluate(() =>
          [...document.fonts].some(
            (face) => /Manrope/.test(face.family) && face.status === 'loaded',
          ),
        ),
      )
      .toBe(true);
    const canonical = createHash('sha256')
      .update(await readFile('../brand/fonts/manrope-latin-wght-normal.woff2'))
      .digest('hex');
    const hashes = await Promise.all(received);
    expect(hashes.length).toBeGreaterThan(0);
    expect(hashes.every((hash) => canonical === hash)).toBe(true);
    const faces = await page.evaluate(() =>
      [...document.fonts]
        .filter((face) => /Manrope/.test(face.family) && face.status === 'loaded')
        .map((face) => face.family.replaceAll('"', '')),
    );
    expect(
      await page.evaluate(() =>
        [...document.fonts].some(
          (face) =>
            /KoinonManrope/.test(face.family) &&
            face.weight === '200 800' &&
            face.status === 'loaded',
        ),
      ),
    ).toBe(true);
    const family = await page
      .locator('ffk-library-template button')
      .first()
      .evaluate((el) => getComputedStyle(el).fontFamily);
    expect(faces.some((face) => family.includes(face))).toBe(true);
  });
test('two embedded workbenches share an asset face and release it without changing host typography', async ({
  page,
}) => {
  let fontRequests = 0;
  page.on('request', (request) => {
    if (/manrope.*\.woff2/i.test(request.url())) fontRequests++;
  });
  await mockService(page);
  await page.goto('/elements/');
  await page.waitForFunction(() => !!customElements.get('firefly-koinon'));
  const hostFamily = await page.locator('body').evaluate((el) => getComputedStyle(el).fontFamily);
  await page.evaluate(async () => {
    const sdk = await import('/sdk/index.js');
    const second = document.createElement('firefly-koinon') as HTMLElement & {
      client: unknown;
      tenantId: string;
      showNavigation: boolean;
      brandBase: string;
    };
    second.brandBase = '/elements/assets/brand';
    second.tenantId = 'tenant-one';
    second.showNavigation = false;
    second.client = new sdk.KoinonClient({
      transport: new sdk.FetchTransport({ baseUrl: '/bff/api/v1' }),
    });
    document.body.append(second);
  });
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          [...document.fonts].filter(
            (face) => /KoinonManrope/.test(face.family) && face.status === 'loaded',
          ).length,
      ),
    )
    .toBe(1);
  await expect(
    page.getByRole('button', { name: 'Research operations', exact: true }),
  ).toBeVisible();
  expect(fontRequests).toBe(1);
  await page.evaluate(() => document.querySelector('firefly-koinon')?.remove());
  expect(
    await page.evaluate(
      () => [...document.fonts].filter((face) => /KoinonManrope/.test(face.family)).length,
    ),
  ).toBe(1);
  await expect(page.locator('body')).toHaveCSS('font-family', hostFamily);
  await page.evaluate(() => document.querySelector('firefly-koinon')?.remove());
  await expect
    .poll(() =>
      page.evaluate(
        () => [...document.fonts].filter((face) => /KoinonManrope/.test(face.family)).length,
      ),
    )
    .toBe(0);
});
