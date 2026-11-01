// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService } from './fixtures';

const photo = Buffer.from(
  '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDlqKKKDyAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/2Q==',
  'base64',
);

test('a personal photo is previewed, explicitly saved, restored after reload and removed', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockService(page);
  let writes = 0;
  let profile = {
    subject: 'synthetic.reviewer',
    display_name: 'Alex Rivera',
    locale: 'en-US',
    time_zone: 'UTC',
    response_language: 'auto',
    avatar_url: null as string | null,
    avatar_version: null as string | null,
  };
  await page.route('**/bff/api/v1/profile**', async (route) => {
    const request = route.request(),
      url = new URL(request.url());
    if (url.pathname.endsWith('/profile/avatar')) {
      if (request.method() === 'GET')
        return route.fulfill({ contentType: 'image/jpeg', body: photo });
      expect(request.headers()['x-xsrf-token']).toBe('synthetic-csrf+token');
      if (request.method() === 'POST') {
        expect(request.headers()['content-type']).toBe('image/jpeg');
        expect(request.postDataBuffer()).toEqual(photo);
        writes++;
        profile = {
          ...profile,
          avatar_url: '/api/v1/profile/avatar',
          avatar_version: 'saved-photo',
        };
      } else if (request.method() === 'DELETE')
        profile = { ...profile, avatar_url: null, avatar_version: null };
    }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(profile) });
  });
  const open = async () => {
    await page.getByRole('button', { name: 'Account menu', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Your account', exact: true }).click();
  };
  await page.goto('/library');
  await open();
  const panel = page.locator('ffk-account-panel');
  const select = () =>
    panel
      .getByLabel('Choose photo', { exact: true })
      .setInputFiles({ name: 'profile-photo.jpg', mimeType: 'image/jpeg', buffer: photo });
  await select();
  await expect(panel.getByRole('img', { name: 'Profile photo', exact: true })).toBeVisible();
  expect(writes).toBe(0);
  await panel.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Save photo', exact: true })).toHaveCount(0);
  expect(writes).toBe(0);
  await select();
  await panel.getByRole('button', { name: 'Save photo', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Remove photo', exact: true })).toBeVisible();
  expect(writes).toBe(1);
  await page.reload();
  await open();
  await expect(panel.getByRole('img', { name: 'Profile photo', exact: true })).toBeVisible();
  await expect(panel.getByRole('img', { name: 'Profile photo', exact: true })).toHaveJSProperty(
    'naturalWidth',
    64,
  );
  const folder = resolve(
    process.env['KOINON_DIRECTORY_CAPTURES'] ??
      '../../control/frontend-captures/organization-directory',
  );
  await mkdir(folder, { recursive: true });
  await page.evaluate(() => {
    document
      .querySelector<HTMLElement>('ffk-workbench')
      ?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 22px)');
    const note = document.createElement('div');
    note.textContent = 'Interface preview using controlled service data.';
    note.style.cssText =
      'position:fixed;bottom:0;inset-inline:0;z-index:99999;padding:5px;background:#855414;color:white;text-align:center;font:10px Manrope,sans-serif';
    document.body.append(note);
  });
  await page.screenshot({ path: resolve(folder, 'profile-photo-1440.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 1000 });
  await expect(panel.getByRole('button', { name: 'Remove photo', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.screenshot({ path: resolve(folder, 'profile-photo-390.png'), fullPage: true });
  await panel.getByRole('button', { name: 'Remove photo', exact: true }).click();
  await expect(panel.getByRole('img', { name: 'Profile photo', exact: true })).toHaveCount(0);
  expect(writes).toBe(1);
});
