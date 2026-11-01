// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page, type Locator } from '@playwright/test';
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { mockService } from './fixtures';
async function installation(page: Page) {
  await mockService(page);
  const brand = {
    product_name: 'Northstar Knowledge',
    assistant_name: 'Northstar',
    font_family: 'Inter',
  };
  await page.route('**/bff/api/v1/branding/defaults', (route) => route.fulfill({ json: brand }));
  await page.route('**/bff/api/v1/tenants/*/branding', (route) =>
    route.fulfill({ status: 404, json: {} }),
  );
  const received: Promise<string>[] = [];
  page.on('response', (response) => {
    if (/inter-latin-wght-normal\.woff2/.test(response.url()))
      received.push(
        response.body().then((bytes) => createHash('sha256').update(bytes).digest('hex')),
      );
  });
  return received;
}
async function usesInter(page: Page, element: Locator, received: Promise<string>[]) {
  await expect(element).toBeVisible();
  await expect
    .poll(() => element.evaluate((node) => getComputedStyle(node).fontFamily))
    .toContain('KoinonInter');
  const expected = createHash('sha256')
    .update(await readFile('../brand/fonts/inter-latin-wght-normal.woff2'))
    .digest('hex');
  const hashes = await Promise.all(received);
  expect(hashes.length).toBeGreaterThan(0);
  expect(hashes.every((hash) => hash === expected)).toBe(true);
  expect(
    await page.locator('body').evaluate((node) => getComputedStyle(node).fontFamily),
  ).not.toContain('KoinonInter');
}
test('installation Inter is loaded on the unauthenticated sign-in screen', async ({ page }) => {
  const received = await installation(page);
  await page.route('**/bff/api/v1/context', (route) =>
    route.fulfill({ status: 401, json: { detail: 'Sign in' } }),
  );
  await page.goto('/library');
  await usesInter(
    page,
    page.getByRole('heading', { name: 'Welcome to Northstar Knowledge' }),
    received,
  );
});
test('standalone account route retains installation Inter and leaves host body typography scoped', async ({
  page,
}) => {
  const received = await installation(page);
  await page.goto('/account/profile');
  await usesInter(page, page.getByRole('textbox', { name: 'Display name', exact: true }), received);
});
test('failed logout session notice uses the selected installation font', async ({ page }) => {
  const received = await installation(page);
  await page.route('**/logout', (route) => route.fulfill({ status: 503, json: {} }));
  await page.route('**/auth/me', (route) => route.fulfill({ json: { authenticated: true } }));
  await page.goto('/library');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Sign out', exact: true }).click();
  await page.getByRole('dialog', { name: 'Sign out?', exact: true }).getByRole('button', { name: 'Sign out', exact: true }).click();
  await usesInter(
    page,
    page.getByRole('alert').filter({ hasText: 'You are still signed in' }),
    received,
  );
});

test('successful logout returns to the installation-branded sign-in screen', async ({ page }) => {
  const received = await installation(page);
  let signedOut = false;
  await page.route('**/bff/api/v1/context', async (route) => {
    if (signedOut) await route.fulfill({ status: 401, json: { detail: 'Sign in' } });
    else await route.fallback();
  });
  await page.route('**/auth/me', (route) => route.fulfill({ status: 401, json: {} }));
  await page.route('**/logout', (route) => {
    signedOut = true;
    return route.fulfill({ status: 204 });
  });
  await page.goto('/library');
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Sign out', exact: true }).click();
  await page.getByRole('dialog', { name: 'Sign out?', exact: true }).getByRole('button', { name: 'Sign out', exact: true }).click();
  await usesInter(
    page,
    page.getByRole('heading', { name: 'Welcome to Northstar Knowledge' }),
    received,
  );
  await expect(page.locator('.auth-scene')).toBeVisible();
  await expect.poll(()=>page.locator('.auth-scene').evaluate((image:HTMLImageElement)=>image.naturalWidth)).toBeGreaterThan(0);
  const output=process.env['KOINON_AUTH_SCREENSHOTS'];if(output){await mkdir(output,{recursive:true});await page.screenshot({path:output+'/auth-library-signed-out.png',fullPage:true});}

});
