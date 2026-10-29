// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// Controlled fixtures prove UI policy requests, not native engine or live-provider acceptance.
import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mockService, context } from './fixtures';
import {
  documents,
  structured,
  knowledgeBehaviorSettings as settings,
} from './knowledge-behavior-fixture';
async function open(
  page: Page,
  options: { spanish?: boolean; readOnly?: boolean; conflict?: boolean; embedded?: boolean } = {},
) {
  await mockService(page);
  const writes: unknown[] = [];
  if (options.readOnly)
    await page.route('**/bff/api/v1/context', (route) =>
      route.fulfill({
        json: {
          ...context,
          tenants: context.tenants.map((tenant) => ({
            ...tenant,
            permissions: tenant.permissions.filter((permission) => permission !== 'settings:write'),
          })),
        },
      }),
    );
  if (options.spanish)
    await page.route('**/bff/api/v1/profile', (route) =>
      route.fulfill({
        json: {
          subject: context.subject,
          display_name: 'Alex Rivera',
          locale: 'es-ES',
          time_zone: 'UTC',
          response_language: 'es',
          avatar_url: null,
        },
      }),
    );
  await page.route('**/bff/api/v1/tenants/*/knowledge/settings', async (route) => {
    if (route.request().method() === 'PUT') {
      const body = route.request().postDataJSON();
      writes.push(body);
      if (options.conflict)
        return route.fulfill({
          status: 409,
          json: {
            code: 'ORGANIZATION_KNOWLEDGE_CHANGED',
            detail: 'Changed by another administrator',
          },
        });
      return route.fulfill({
        json: {
          ...settings,
          documents: body.documents,
          structured: body.structured,
          revision: 8,
          origin: 'organization',
        },
      });
    }
    return route.fulfill({ json: settings });
  });
  await page.goto(options.embedded ? '/elements/' : '/');
  if (options.embedded) {
    await page.waitForFunction(() => !!customElements.get('firefly-koinon'));
    await page.evaluate(async () => {
      const sdk = await import('/sdk/index.js');
      const element = document.querySelector('firefly-koinon') as HTMLElement & {
        client: unknown;
        tenantId: string;
        showNavigation: boolean;
        view: string;
      };
      element.style.setProperty('--koinon-workspace-height', '640px');
      element.tenantId = 'tenant-one';
      element.showNavigation = false;
      element.view = 'settings';
      element.client = new sdk.KoinonClient({
        transport: new sdk.FetchTransport({ baseUrl: '/bff/api/v1', credentials: 'include' }),
      });
    });
  } else {
    const menu = page.getByRole('button', {
      name: options.spanish ? 'Abrir navegación' : 'Open navigation',
      exact: true,
    });
    if ((page.viewportSize()?.width ?? 1440) < 760) await menu.click();
    await page
      .getByRole('button', { name: options.spanish ? 'Configuración' : 'Settings', exact: true })
      .click();
  }
  await expect(page.locator('ffk-settings-page')).toBeVisible();
  const select = page.getByRole('combobox', {
    name: options.spanish ? 'Sección de configuración' : 'Settings section',
    exact: true,
  });
  if ((page.viewportSize()?.width ?? 1440) < 760) await select.selectOption('models');
  else
    await page
      .getByRole('button', {
        name: options.spanish ? 'Modelos de conocimiento' : 'Knowledge models',
        exact: true,
      })
      .click();
  await expect(page.locator('ffk-knowledge-behavior input[type=radio]').first()).toBeVisible();
  await expect(page.locator('ffk-knowledge-behavior .origin')).toContainText(
    options.spanish ? 'Guardado para esta organización' : 'Saved for this organization',
  );
  await expect(page.locator('ffk-knowledge-behavior .origin')).toContainText(
    options.spanish ? 'Revisión 7' : 'Revision 7',
  );
  return { writes, panel: page.locator('ffk-knowledge-behavior') };
}
for (const width of [1440, 390])
  test(`organization behavior saves bounded document and SQL policy at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const { panel, writes } = await open(page);
    await expect(
      panel.getByRole('heading', { name: 'Knowledge behavior', exact: true }),
    ).toBeVisible();
    await expect(panel).toContainText('Knowledge operations');
    const rlm = panel.getByRole('radio', { name: /Analyze documents in steps/ });
    await rlm.focus();
    await page.keyboard.press('Space');
    await expect(rlm).toBeChecked();
    await expect(panel.getByText('RLM uses document files', { exact: true })).toBeVisible();
    await panel
      .locator('summary')
      .filter({ hasText: /^Document analysis$/ })
      .click();
    await panel.getByRole('spinbutton', { name: 'Analysis calls', exact: true }).fill('0');
    await panel
      .locator('summary')
      .filter({ hasText: /^Dataset queries$/ })
      .click();
    await panel
      .getByRole('spinbutton', { name: 'Minimum grounding confidence', exact: true })
      .fill('0.75');
    await panel.getByRole('button', { name: 'Save changes', exact: true }).click();
    await expect(panel.getByRole('status')).toContainText('Knowledge behavior saved.');
    expect(writes).toEqual([
      {
        expected_revision: 7,
        documents: { ...documents, answer_mode: 'rlm', rlm_sub_budget: 0 },
        structured: { ...structured, grounding_min_confidence: 0.75 },
      },
    ]);
    await expect(panel.getByRole('button', { name: 'Save changes', exact: true })).toBeDisabled();
    const geometry = await panel.evaluate((element) => ({
      width: element.getBoundingClientRect().width,
      right: element.getBoundingClientRect().right,
      viewport: innerWidth,
      overflow: document.documentElement.scrollWidth > innerWidth,
    }));
    expect(geometry.right).toBeLessThanOrEqual(geometry.viewport);
    expect(geometry.overflow).toBe(false);
    for (const button of await panel.getByRole('button').all()) {
      const box = await button.boundingBox();
      if (box) expect(box.height).toBeGreaterThanOrEqual(width === 390 ? 44 : 40);
    }
    const directory = process.env['KOINON_UI_CAPTURE_DIR'] ?? 'test-results/knowledge-behavior';
    await mkdir(directory, { recursive: true });
    for (const [label, filename] of [
      ['Document analysis', 'analysis'],
      ['Dataset queries', 'sql'],
    ]) {
      const details = panel.locator('details').filter({
        has: page.locator('summary').filter({ hasText: new RegExp('^' + label + '$') }),
      });
      if (width === 390 && filename === 'sql') {
        await details.locator('summary').scrollIntoViewIfNeeded();
        await page.screenshot({
          path: resolve(directory, 'knowledge-behavior-sql-top-390.png'),
          animations: 'disabled',
        });
        await details
          .getByRole('spinbutton', { name: 'Metric matches', exact: true })
          .scrollIntoViewIfNeeded();
        await page.screenshot({
          path: resolve(directory, 'knowledge-behavior-sql-middle-390.png'),
          animations: 'disabled',
        });
        await details.getByRole('spinbutton').last().scrollIntoViewIfNeeded();
        await page.screenshot({
          path: resolve(directory, 'knowledge-behavior-sql-bottom-390.png'),
          animations: 'disabled',
        });
      } else {
        await details.screenshot({
          path: resolve(directory, `knowledge-behavior-${filename}-${width}.png`),
          animations: 'disabled',
        });
      }
    }
    await panel
      .locator('summary')
      .filter({ hasText: /^Document analysis$/ })
      .click();
    await panel
      .locator('summary')
      .filter({ hasText: /^Dataset queries$/ })
      .click();
    await page.locator('.settings-content').evaluate((element) => (element.scrollTop = 0));
    await page.screenshot({
      path: resolve(directory, `knowledge-behavior-${width}.png`),
      animations: 'disabled',
    });
  });
test('provider administrator can read behavior without organization settings authority', async ({
  page,
}) => {
  const { panel, writes } = await open(page, { readOnly: true });
  await expect(panel.getByRole('radio').first()).toBeDisabled();
  await expect(panel.getByRole('button', { name: 'Save changes', exact: true })).toBeDisabled();
  expect(writes).toEqual([]);
});
test('conflict retains the selected method and requires reload', async ({ page }) => {
  const { panel, writes } = await open(page, { conflict: true });
  await panel.getByRole('radio', { name: /Analyze documents in steps/ }).check();
  await panel.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('Reload');
  await expect(panel.getByRole('radio', { name: /Analyze documents in steps/ })).toBeChecked();
  await expect(panel.getByRole('button', { name: 'Save changes', exact: true })).toBeDisabled();
  await panel.getByRole('button', { name: 'Reload knowledge behavior', exact: true }).click();
  await expect(panel.getByRole('radio', { name: /Find relevant passages/ })).toBeChecked();
  expect(writes).toHaveLength(1);
});
test('Spanish lazy settings keeps document methods separate from SQL controls', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 1000 });
  const { panel } = await open(page, { spanish: true });
  await expect(
    panel.getByRole('heading', { name: 'Comportamiento del conocimiento', exact: true }),
  ).toBeVisible();
  await panel
    .locator('summary')
    .filter({ hasText: /^Consultas de datos$/ })
    .click();
  await expect(
    panel.getByRole('spinbutton', { name: 'Confianza mínima del contexto', exact: true }),
  ).toHaveValue('0.6');
  await expect(panel.getByRole('radio')).toHaveCount(2);
});
for (const variant of [
  { width: 1440, embedded: false },
  { width: 390, embedded: false },
  { width: 390, embedded: true },
])
  test(`dirty knowledge actions stay reachable without covering focused controls at ${variant.width}px${variant.embedded ? ' embedded' : ''}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: variant.width, height: 1000 });
    const { panel, writes } = await open(page, variant);
    const rlm = panel.getByRole('radio', { name: /Analyze documents in steps/ });
    await rlm.focus();
    await page.keyboard.press('Space');
    const save = panel.getByRole('button', { name: 'Save changes', exact: true });
    const cancel = panel.getByRole('button', { name: 'Cancel', exact: true });
    await expect(save).toBeEnabled();
    await expect(save).toHaveCount(1);
    const geometry = await save.evaluate((element) => {
      const button = element.getBoundingClientRect(),
        port = element.closest('.settings-content')!.getBoundingClientRect();
      const shellFooter = element
        .closest('ffk-shell')!
        .querySelector('.shell > .main > footer')!
        .getBoundingClientRect();
      const bar = element.closest('footer')!,
        barTop = bar.getBoundingClientRect().top;
      const actionBorder = parseFloat(getComputedStyle(bar).borderTopWidth);
      const nearbySectionRules = [
        ...element.closest('ffk-knowledge-behavior')!.querySelectorAll('details'),
      ]
        .map((section) => section.getBoundingClientRect().top)
        .filter((top) => top >= barTop - 4 && top < barTop);
      return {
        actionBorder,
        barTop,
        nearbySectionRules,
        top: button.top,
        bottom: button.bottom,
        height: button.height,
        portTop: port.top,
        portBottom: port.bottom,
        shellFooterTop: shellFooter.top,
      };
    });
    await testInfo.attach('dirty-action-geometry', {
      body: JSON.stringify(geometry),
      contentType: 'application/json',
    });
    expect(geometry.actionBorder > 0 && geometry.nearbySectionRules.length > 0).toBe(false);
    expect(geometry.top).toBeGreaterThanOrEqual(geometry.portTop);
    expect(geometry.bottom).toBeLessThanOrEqual(geometry.portBottom);
    expect(geometry.bottom).toBeLessThanOrEqual(geometry.shellFooterTop);
    expect(geometry.height).toBeGreaterThanOrEqual(variant.width === 390 ? 44 : 40);
    await expect(panel.locator('.limitation')).not.toContainText('KNOWLEDGE_RLM_UNQUALIFIED');
    const directory = process.env['KOINON_UI_CAPTURE_DIR'] ?? 'test-results/knowledge-behavior';
    await mkdir(directory, { recursive: true });
    await page.screenshot({
      path: resolve(
        directory,
        `knowledge-dirty-actions-${variant.width}${variant.embedded ? '-embedded' : ''}.png`,
      ),
      animations: 'disabled',
    });
    await save.focus();
    await expect(save).toBeFocused();
    await panel
      .locator('summary')
      .filter({ hasText: /^Dataset queries$/ })
      .click();
    const last = panel.getByRole('spinbutton', {
      name: 'Minimum grounding confidence',
      exact: true,
    });
    await last.focus();
    await expect(last).toBeFocused();
    const inputBox = await last.boundingBox(),
      barBox = await panel.locator('footer').boundingBox();
    expect(inputBox!.y + inputBox!.height + 2).toBeLessThanOrEqual(barBox!.y);
    await cancel.click();
    await expect(panel.getByRole('radio', { name: /Find relevant passages/ })).toBeChecked();
    await expect(save).toBeDisabled();
    expect(writes).toEqual([]);
  });
