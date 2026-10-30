// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService, context } from './fixtures';
const token = 'synthetic_private_invitation_'.padEnd(43, 'a');
async function invitation(page: Page, signedIn = true) {
  await mockService(page);
  const state = {
    accepted: false,
    signedIn,
    unavailable: false,
    contextReads: 0,
    inspections: 0,
    redemptions: 0,
  };
  await page.route('**/bff/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (value: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
    if (path.endsWith('/context')) {
      ++state.contextReads;
      return state.signedIn
        ? json({
            ...context,
            tenants: state.accepted ? [context.tenants[0]] : [],
            workspaces: state.accepted ? context.workspaces : [],
          })
        : json({ detail: 'Sign in is required' }, 401);
    }
    if (path.endsWith('/invitations/inspect')) {
      ++state.inspections;
      if (state.unavailable) return json({ detail: 'Controlled unavailable invitation' }, 404);
      expect(route.request().postDataJSON()).toEqual({ token });
      return json({
        id: 'invitation',
        tenant_id: 'tenant-one',
        tenant_name: 'Knowledge operations',
        workspace_id: 'workspace-one',
        workspace_name: 'Research operations',
        role: 'editor',
        expires_at: '2026-11-01T12:00:00Z',
      });
    }
    if (path.endsWith('/invitations/redeem')) {
      ++state.redemptions;
      state.accepted = true;
      return json({
        id: 'membership',
        tenant_id: 'tenant-one',
        subject: context.subject,
        workspace_id: 'workspace-one',
        role: 'editor',
        active: true,
      });
    }
    return route.fallback();
  });
  return state;
}
test('an invited user with no organizations can review and accept access before the library opens', async ({
  page,
}) => {
  const state = await invitation(page);
  const urls: string[] = [];
  page.on('request', (request) => urls.push(request.url()));
  await page.goto('/#invite=' + token);
  await expect(page.getByRole('heading', { name: 'Join an organization' })).toBeVisible();
  expect(new URL(page.url()).hash).toBe('');
  expect(state.redemptions).toBe(0);
  const output = resolve(process.cwd(), '../../../outputs');
  await mkdir(output, { recursive: true });
  await page.addStyleTag({
    content: 'ffk-workbench{--koinon-workspace-height:calc(100dvh - 22px)}',
  });
  await page.evaluate(() => {
    const label = document.createElement('div');
    label.textContent = 'Controlled service fixtures, Invitation review';
    Object.assign(label.style, {
      position: 'fixed',
      inset: 'auto 0 0',
      height: '22px',
      background: '#855414',
      color: '#fff',
      font: '11px/22px system-ui',
      textAlign: 'center',
      zIndex: '9999',
    });
    document.body.append(label);
  });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      width,
    );
    await page.screenshot({
      path: resolve(output, `koinon-invitation-${width}.png`),
      animations: 'disabled',
    });
  }
  await page.getByRole('button', { name: 'Accept invitation', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('ffk-shell')).toBeVisible();
  expect(state.redemptions).toBe(1);
  expect(state.contextReads).toBeGreaterThanOrEqual(2);
  expect(await page.evaluate(() => sessionStorage.getItem('koinon.pending-invitation'))).toBeNull();
  expect(urls.some((url) => url.includes(token))).toBe(false);
});
test('keeps the private link across authentication and requires explicit acceptance', async ({
  page,
}) => {
  const state = await invitation(page, false);
  await page.goto('/#invite=' + token);
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
  expect(state.inspections).toBe(0);
  state.signedIn = true;
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Join an organization' })).toBeVisible();
  await page.getByRole('button', { name: 'Not now', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Join an organization' })).toHaveCount(0);
  expect(state.redemptions).toBe(0);
  expect(await page.evaluate(() => sessionStorage.getItem('koinon.pending-invitation'))).toBeNull();
});

test('an unavailable invitation can be closed without granting access and restores keyboard focus', async ({
  page,
}) => {
  const state = await invitation(page);
  state.unavailable = true;
  await page.goto('/#invite=' + token);
  await expect(page.getByRole('alert')).toContainText('This invitation is unavailable.');
  await page.getByRole('button', { name: 'Close invitation', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Join an organization' })).toHaveCount(0);
  await expect(page.locator('ffk-shell h1')).toBeFocused();
  expect(state.redemptions).toBe(0);
  expect(await page.evaluate(() => sessionStorage.getItem('koinon.pending-invitation'))).toBeNull();
});
