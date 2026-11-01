// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { KnowledgeConnection, KnowledgeRole } from '@fireflyframework/koinon-sdk';
import { openAdministration,  mockService, context as contextFixture, entry, setDarkAppearance } from './fixtures';
const roles: KnowledgeRole[] = [
  {
    id: 'documents.answer',
    domain: 'documents',
    label: 'Document answer and query expansion',
    kind: 'generative',
    purposes: ['search', 'answer'],
    supports_current_agent: true,
    compatible_index_required: false,
    assignment: null,
    status: 'needs_setup',
    runtime_qualification: 'not_run',
  },
  {
    id: 'documents.embedding',
    domain: 'documents',
    label: 'Document embeddings',
    kind: 'embedding',
    purposes: ['ingest', 'search'],
    supports_current_agent: false,
    compatible_index_required: true,
    assignment: null,
    status: 'needs_setup',
    runtime_qualification: 'not_run',
  },
  {
    id: 'structured.embedding',
    domain: 'structured',
    label: 'Structured schema embeddings',
    kind: 'embedding',
    purposes: ['ingest', 'query'],
    supports_current_agent: false,
    compatible_index_required: true,
    assignment: null,
    status: 'needs_setup',
    runtime_qualification: 'not_run',
  },
];
async function fixture(page: Page, spanish = false) {
  await mockService(page);
  const rows: KnowledgeConnection[] = [];
  const writes: { method: string; query: URLSearchParams; body: Record<string, unknown> | null }[] =
    [];
  let rejectEmbedding = false;
  await page.route('**/bff/api/v1/**', async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname;
    const json = (value: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
    if (path.endsWith('/context'))
      return json({
        ...contextFixture,
        workspaces: [
          ...contextFixture.workspaces,
          entry('other-space', 'workspace', 'Other organization space', null, {
            tenant_id: 'tenant-two',
          }),
          entry('archived-space', 'workspace', 'Archived space', null, { status: 'archived' }),
        ],
      });
    if (spanish && path.endsWith('/profile'))
      return json({
        subject: 'synthetic.reviewer',
        display_name: 'Alex Rivera',
        locale: 'es-ES',
        time_zone: 'Europe/Madrid',
        response_language: 'es',
        avatar_url: null,
        avatar_version: null,
      });
    if (!path.endsWith('/knowledge-roles') && !path.includes('/knowledge-connections'))
      return route.fallback();
    const scope = url.searchParams.get('workspace_id');
    if (request.method() === 'GET') {
      if (path.endsWith('/knowledge-roles'))
        return json({
          roles: roles.map((role) => {
            const row =
              rows.find((row) => row.role === role.id && row.workspace_id === scope) ??
              rows.find((row) => row.role === role.id && row.workspace_id === null);
            return {
              ...role,
              assignment: row ? (row.workspace_id ? 'workspace' : 'tenant') : null,
              status: row ? (row.enabled ? 'assigned' : 'disabled') : 'needs_setup',
            };
          }),
          model_options_schema: { properties: {} },
          providers: [
            {
              id: 'model-provider',
              name: 'Controlled native model',
              kind: 'ollama',
              api: 'chat',
              model_ids: ['qualified-chat', 'qualified-embedding'],
              enabled: true,
            },
          ],
        });
      return json({ items: rows.filter((row) => row.workspace_id === scope) });
    }
    expect(request.headers()['x-xsrf-token']).toBe('synthetic-csrf+token');
    const body =
      request.method() === 'DELETE' ? null : (request.postDataJSON() as Record<string, unknown>);
    writes.push({ method: request.method(), query: url.searchParams, body });
    if (rejectEmbedding && body?.['role'] === 'documents.embedding')
      return json(
        {
          code: 'KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED',
          detail: 'This indexed space needs a reviewed reindex',
        },
        409,
      );
    const identifier = path.split('/').at(-1),
      previous = rows.find((row) => row.id === identifier);
    if (request.method() === 'DELETE') {
      expect(url.searchParams.get('expected_revision')).toBe(String(previous?.revision));
      rows.splice(rows.indexOf(previous!), 1);
      return json({ deleted: true });
    }
    if (previous) {
      expect(body?.['expected_revision']).toBe(previous.revision);
      Object.assign(previous, body, { revision: previous.revision + 1 });
      return json(previous);
    }
    expect(body).not.toHaveProperty('expected_revision');
    expect(body).not.toHaveProperty('secret');
    const row = {
      id: 'binding-' + rows.length,
      tenant_id: 'tenant-one',
      workspace_id: null,
      mode: 'provider',
      provider_id: null,
      model_id: null,
      model_options: {},
      dimensions: null,
      storage_dimensions: null,
      space_id: null,
      embedding_fingerprint: null,
      enabled: true,
      revision: 1,
      created_by: 'synthetic.reviewer',
      updated_by: 'synthetic.reviewer',
      created_at: '2026-10-27T12:00:00Z',
      updated_at: '2026-10-27T12:00:00Z',
      ...body,
    } as KnowledgeConnection;
    rows.push(row);
    return json(row, 201);
  });
  return {
    rows,
    writes,
    rejectEmbeddings: () => {
      rejectEmbedding = true;
    },
  };
}
async function open(page: Page, mobile = false, spanish = false) {
  await page.goto('/library');
  if (mobile)
    await page
      .getByRole('button', { name: spanish ? 'Abrir navegación' : 'Open navigation', exact: true })
      .click();
  await openAdministration(page, spanish ? 'Configuración' : 'Settings');
  if (mobile)
    await page
      .getByRole('combobox', {
        name: spanish ? 'Sección de configuración' : 'Settings section',
        exact: true,
      })
      .selectOption('models');
  else await page.getByRole('button', { name: 'Knowledge models', exact: true }).click();
  await expect(
    page.getByRole('heading', {
      name: spanish ? 'Modelos de conocimiento' : 'Knowledge models',
      exact: true,
    }),
  ).toBeVisible();
}
test('operator assigns an organization default, overrides it for a space and restores inheritance', async ({
  page,
}) => {
  const service = await fixture(page);
  await open(page);
  await expect(
    page.getByRole('combobox', { name: 'Assignment scope', exact: true }).locator('option'),
  ).toHaveCount(2);
  await expect(
    page
      .getByRole('combobox', { name: 'Assignment scope', exact: true })
      .locator('option', { hasText: 'Other organization space' }),
  ).toHaveCount(0);
  await page
    .getByRole('button', { name: 'Configure Document answer and query expansion', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Document answer and query expansion', exact: true }),
  ).toBeFocused();
  await page
    .getByRole('combobox', { name: 'Model provider', exact: true })
    .selectOption('model-provider');
  await page.getByRole('combobox', { name: 'Model', exact: true }).selectOption('qualified-chat');
  await page.getByRole('button', { name: 'Save assignment', exact: true }).click();
  expect(service.writes[0].body).toEqual({
    domain: 'documents',
    role: 'documents.answer',
    workspace_id: null,
    mode: 'provider',
    enabled: true,
    provider_id: 'model-provider',
    model_id: 'qualified-chat',
    model_options: {},
  });
  await expect(page.getByText('Ready', { exact: true })).toHaveCount(0);
  await page.getByRole('combobox', { name: /^Assignment scope/ }).selectOption('workspace-one');
  await expect(page.getByText('Uses organization default', { exact: true })).toBeVisible();
  await page
    .getByRole('button', { name: 'Customize Document answer and query expansion', exact: true })
    .click();
  await page
    .getByRole('combobox', { name: 'Model selection', exact: true })
    .selectOption('current_agent');
  await expect(
    page.getByText(
      'This choice works only during a chat run. Operations outside Chat need a separate model assignment.',
      { exact: true },
    ),
  ).toBeVisible();
  await page.getByRole('checkbox', { name: 'Enable this assignment', exact: true }).uncheck();
  await expect(
    page.getByText('A disabled workspace override blocks the organization default for this role.', {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Save assignment', exact: true }).click();
  expect(service.writes[1].body).toEqual({
    domain: 'documents',
    role: 'documents.answer',
    workspace_id: 'workspace-one',
    mode: 'current_agent',
    enabled: false,
  });
  await page
    .getByRole('button', { name: 'Configure Document answer and query expansion', exact: true })
    .click();
  await page.getByRole('button', { name: 'Remove workspace override', exact: true }).click();
  await page.getByRole('button', { name: 'Remove assignment', exact: true }).click();
  expect(service.writes.at(-1)?.method).toBe('DELETE');
  expect(service.writes.at(-1)?.query.get('expected_revision')).toBe('1');
  await expect(page.getByText('Uses organization default', { exact: true })).toBeVisible();
  await expect(
    page.getByRole('button', {
      name: 'Customize Document answer and query expansion',
      exact: true,
    }),
  ).toBeFocused();
});
test('embedding form blocks incompatible dimensions and preserves a native reindex refusal', async ({
  page,
}) => {
  const service = await fixture(page);
  service.rejectEmbeddings();
  await open(page);
  await page.getByRole('button', { name: 'Configure Document embeddings', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Model selection', exact: true })).toHaveCount(0);
  await page
    .getByRole('combobox', { name: 'Model provider', exact: true })
    .selectOption('model-provider');
  await page
    .getByRole('combobox', { name: 'Model', exact: true })
    .selectOption('qualified-embedding');
  await page.getByRole('textbox', { name: 'Model dimensions', exact: true }).fill('768');
  await page.getByRole('textbox', { name: 'Storage dimensions', exact: true }).fill('1536');
  await page
    .getByRole('textbox', { name: 'Approved index reference', exact: true })
    .fill('approved-existing-index');
  await page.getByRole('button', { name: 'Save assignment', exact: true }).click();
  await expect(
    page.getByText('Document model and storage dimensions must match.', { exact: true }).last(),
  ).toBeVisible();
  expect(service.writes).toHaveLength(0);
  await page.getByRole('textbox', { name: 'Storage dimensions', exact: true }).fill('768');
  await page.getByRole('button', { name: 'Save assignment', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText(
    'Ask your deployment administrator to complete a reviewed reindex',
  );
  expect(service.rows).toHaveLength(0);
  await expect(page.getByRole('button', { name: 'Save assignment', exact: true })).toBeVisible();
});
for (const { width, dark } of [
  { width: 1440, dark: false },
  { width: 390, dark: false },
  { width: 390, dark: true },
])
  test(`controlled knowledge model form ${width}${dark ? ' dark' : ''}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const spanish = width === 390;
    await fixture(page, spanish);
    await open(page, width < 700, spanish);
    if (dark) await setDarkAppearance(page, spanish);
    await page
      .getByRole('button', {
        name: spanish
          ? 'Configurar Representaciones vectoriales de documentos'
          : 'Configure Document embeddings',
        exact: true,
      })
      .click();
    await page
      .getByRole('combobox', {
        name: spanish ? 'Proveedor del modelo' : 'Model provider',
        exact: true,
      })
      .selectOption('model-provider');
    await page
      .getByRole('combobox', { name: spanish ? 'Modelo' : 'Model', exact: true })
      .selectOption('qualified-embedding');
    await page
      .getByRole('textbox', {
        name: spanish ? 'Dimensiones del modelo' : 'Model dimensions',
        exact: true,
      })
      .fill('768');
    await page
      .getByRole('textbox', {
        name: spanish ? 'Dimensiones de almacenamiento' : 'Storage dimensions',
        exact: true,
      })
      .fill('768');
    await page
      .getByRole('textbox', {
        name: spanish ? 'Referencia del índice aprobado' : 'Approved index reference',
        exact: true,
      })
      .fill('approved-existing-index');
    await page.evaluate(() => {
      document
        .querySelector<HTMLElement>('ffk-workbench')
        ?.style.setProperty('--koinon-workspace-height', 'calc(100dvh - 22px)');
      const mark = document.createElement('div');
      mark.textContent = 'Interface preview using controlled service data.';
      mark.style.cssText =
        'position:fixed;bottom:0;left:0;right:0;z-index:9999;padding:5px 12px;background:#855414;color:white;font:10px system-ui;pointer-events:none;text-align:center';
      document.body.append(mark);
    });
    const directory = resolve('../../control/frontend-captures/knowledge-models');
    await mkdir(directory, { recursive: true });
    const pane = page.locator('.settings-content');
    await pane.evaluate((el) => {
      el.scrollTop = 0;
    });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({
      path: resolve(directory, `knowledge-models-${width}${dark ? '-dark' : ''}-top.png`),
      fullPage: true,
      animations: 'disabled',
    });
    await pane.evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    });
    await expect(
      page.getByRole('button', {
        name: spanish ? 'Guardar asignación' : 'Save assignment',
        exact: true,
      }),
    ).toBeInViewport();
    await page.screenshot({
      path: resolve(directory, `knowledge-models-${width}${dark ? '-dark' : ''}-actions.png`),
      fullPage: true,
      animations: 'disabled',
    });
  });
test('Spanish Settings translates provider setup and empty-state instructions', async ({
  page,
}) => {
  await fixture(page, true);
  await page.goto('/library');
  await openAdministration(page, 'Configuración');
  await expect(page.getByText('No hay proveedores de modelos', { exact: true })).toBeVisible();
  await expect(
    page.getByText('Conecta un proveedor y comprueba que sus modelos están disponibles.', {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Conectar un modelo', exact: true }).click();
  await expect(
    page.getByText(
      'No hay tipos de proveedor disponibles. Pide al administrador que revise la configuración de la instalación.',
      { exact: true },
    ),
  ).toBeVisible();
});
