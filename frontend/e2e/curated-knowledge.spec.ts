// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test, expect, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { KnowledgeIntent, KnowledgeIntentInput } from '@fireflyframework/koinon-sdk';
import { mockService, context, fixtures } from './fixtures';
const stamp = '2026-10-31T00:00:00Z', hash = 'a'.repeat(64);
const answer = 'The renewal threshold is 47. A service owner reviews every renewal.';
async function controlled(page: Page, mode: 'saved' | 'pending' | 'conflict' | 'denied' = 'saved', scoped = false) {
  const origin = new URL(test.info().project.use.baseURL as string).origin;
  await page.route('**/*', (route) => new URL(route.request().url()).origin === origin ? route.fallback() : route.abort());
  await mockService(page, { organizationAgent: 'agent' });
  if (scoped) await page.route('**/bff/api/v1/context', (route) => route.fulfill({ json: {
    ...context, tenants: context.tenants.map((tenant, index) => index ? tenant : { ...tenant, roles: ['editor'], permissions: ['chat:use', 'catalog:read'] }),
    workspace_permissions: { 'workspace-one': ['chat:use', 'catalog:read', 'catalog:write', 'ingest:write'] },
  } }));
  const thread = { id: 'selected-thread', title: 'Renewal review', title_source: 'manual', revision: 1, folder_id: null, archived_at: null,
    scope: { workspace_id: 'workspace-one', project_id: 'project-one' }, created_at: stamp, updated_at: stamp };
  const calls: { method: string; path: string; body: unknown; key?: string; csrf?: string }[] = [];
  let current: KnowledgeIntent | undefined, previews = 0;
  const receipt = () => ({ operation_id: 'operation', intent_id: current!.id, intent_revision: current!.revision,
    authorization_digest: hash, item_id: current!.target_item_id, native_item_id: 'native-item', native_version_id: 'native-version', version: 1,
    serving_version: current!.action === 'create_published' ? 1 : null, action: current!.action,
    content_sha256: hash, evidence_sha256: hash, committed_at: stamp, retrieval_state: current!.action === 'create_published' ? 'lexical_ready' : 'not_published' });
  await page.route('**/bff/api/v1/tenants/*/**', async (route) => {
    const request = route.request(), path = new URL(request.url()).pathname, method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body });
    if (path.endsWith('/agents')) return json({ items: [{ id: 'agent', name: 'Controlled guide', provider_id: 'provider', model_id: 'fixture', tools: [], scope: {}, instructions: '', enabled: true, revision: 1, status: 'ready', configured: true, can_run: true, checks: [] }] });
    if (path.endsWith('/chat/threads')) return json({ items: [thread], total: 1, page: 1, page_size: 25, pages: 1 });
    if (path.endsWith('/chat/threads/selected-thread')) return json(thread);
    if (path.endsWith('/messages')) return json({ items: [
      { id: 'private-question', role: 'user', text: 'Private planning question not selected for publication.', status: 'completed', citations: [], artifacts: [], created_at: stamp },
      { id: 'unselected-answer', role: 'assistant', text: 'An earlier answer is outside this review.', status: 'completed', citations: [], artifacts: [], created_at: stamp },
      { id: 'selected-answer', role: 'assistant', text: answer, status: 'completed', citations: [], artifacts: [], created_at: stamp },
    ], next_cursor: null });
    if (!path.includes('/knowledge-intents')) return route.fallback();
    const body = method === 'POST' ? request.postDataJSON() : undefined;
    calls.push({ method, path, body, key: request.headers()['idempotency-key'], csrf: request.headers()['x-xsrf-token'] });
    if (path.endsWith('/knowledge-intents') && method === 'POST') {
      if (mode === 'denied') return json({ code: 'ACCESS_DENIED', detail: 'Destination access denied' }, 403);
      const input = body as KnowledgeIntentInput;
      current = { id: 'review-' + ++previews, revision: 1, tenant_id: 'tenant-one', owner_subject: context.subject, action: input.action,
        destination: { id: input.destination_id, workspace_id: 'workspace-one', project_id: 'project-one', name: 'Reference library', ancestry_digest: hash },
        target_item_id: 'new-knowledge', before: null, after: input.content, authorization_digest: hash, remembered_context_present: true,
        evidence: [{ kind: 'document_passage', basis: 'remembered_context', source: { id: 'support', asset_id: 'document-one', kind: 'document', title: 'Reviewed operating policy', quote: 'The renewal threshold is 47.', source_part_id: 'immutable-part', used_revision: 'source-part-sha256:' + hash } }],
        status: 'preview', created_at: stamp, expires_at: '2099-01-01T00:00:00Z' };
      return json(current, 201);
    }
    if (path.endsWith('/confirm')) {
      if (mode === 'conflict') return json({ code: 'KNOWLEDGE_INTENT_CONFLICT', detail: 'Review changed' }, 409);
      if (mode === 'pending') return json({ status: 'pending', operation_id: 'operation', intent_id: current!.id }, 202);
      return json({ status: 'committed', receipt: receipt() });
    }
    if (path.endsWith('/cancel')) return json({ ...current, status: 'cancelled', revision: 2 });
    if (method === 'GET') return json({ ...current, status: 'committed', receipt: receipt() });
    throw Error('Unexpected knowledge request: ' + path);
  });
  return { calls };
}
async function openReview(page: Page) {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Account menu', exact: true })).toBeVisible();
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(page.getByText(answer, { exact: true })).toBeVisible();
  const trigger = page.locator('article.message').filter({ has: page.getByText(answer, { exact: true }) })
    .getByRole('button', { name: 'Save as knowledge', exact: true });
  await trigger.focus(); await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: 'Save as knowledge', exact: true });
  await expect(dialog).toBeVisible();
  return { dialog, trigger };
}
async function author(page: Page) {
  const { dialog, trigger } = await openReview(page);
  await dialog.getByRole('textbox', { name: 'Knowledge title', exact: true }).fill('Reviewed renewal rule');
  await expect(dialog.getByRole('textbox', { name: 'Knowledge text', exact: true })).toHaveValue(answer);
  const workspace = dialog.getByRole('treeitem', { name: fixtures[0].name, exact: true });
  await workspace.focus(); await page.keyboard.press('ArrowRight');
  const project = dialog.getByRole('treeitem', { name: fixtures[1].name, exact: true });
  await expect(project).toBeVisible(); await page.keyboard.press('ArrowDown');
  await expect(project).toBeFocused(); await page.keyboard.press('ArrowRight');
  const collection = dialog.getByRole('treeitem', { name: 'Reference library', exact: true });
  await expect(collection).toBeVisible(); await page.keyboard.press('ArrowDown');
  await expect(collection).toBeFocused(); await page.keyboard.press('Enter');
  await expect(collection).toHaveAttribute('aria-selected', 'true');
  await expect(dialog.getByRole('combobox', { name: 'Save this as', exact: true })).toHaveValue('draft');
  return { dialog, trigger };
}
for (const width of [1440, 390]) test(`reviews exact selected knowledge with keyboard consent and cancellation at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: width < 500 ? 844 : 1000 });
  const api = await controlled(page, 'saved', true);
  const { dialog, trigger } = await author(page);
  expect(api.calls).toHaveLength(0);
  const output = process.env['KOINON_UI_REVIEW_DIR'];
  if (output) { await mkdir(output, { recursive: true }); await page.screenshot({ path: resolve(output, `knowledge-edit-${width}.png`), fullPage: true }); }
  await dialog.getByRole('button', { name: 'Review proposal', exact: true }).click();
  await expect(dialog.getByRole('region', { name: 'Review knowledge changes' })).toBeFocused();
  await expect(dialog.getByText('Reviewed renewal rule', { exact: true })).toBeVisible();
  const confirm = dialog.getByRole('button', { name: 'Confirm and save draft', exact: true });
  await expect(confirm).toBeDisabled();
  const consent = dialog.getByRole('checkbox');
  await expect(consent).not.toBeChecked();
  await consent.focus(); await page.keyboard.press('Space');
  await expect(confirm).toBeEnabled();
  if (output) { await confirm.scrollIntoViewIfNeeded(); await page.screenshot({ path: resolve(output, `knowledge-review-${width}.png`), fullPage: true }); }
  expect(api.calls[0].body).toEqual({ action: 'create_draft', destination_id: 'collection-one', content: { title: 'Reviewed renewal rule', body: answer }, origin: { kind: 'conversation', thread_id: 'selected-thread', message_ids: ['selected-answer'] } });
  await dialog.getByRole('button', { name: 'Edit proposal', exact: true }).click();
  await dialog.getByRole('button', { name: 'Review proposal', exact: true }).click();
  await expect(dialog.getByRole('checkbox')).not.toBeChecked();
  await expect(dialog.getByRole('button', { name: 'Confirm and save draft', exact: true })).toBeDisabled();
  await dialog.getByRole('button', { name: 'Cancel proposal', exact: true }).click();
  await expect(dialog.getByText('The proposal was cancelled. No knowledge was saved.', { exact: true })).toBeVisible();
  expect(api.calls.at(-1)?.body).toEqual({ expected_revision: 1 });
  expect(api.calls.some((call) => call.path.endsWith('/confirm'))).toBe(false);
  expect(api.calls.every((call) => call.csrf === 'synthetic-csrf+token')).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
  await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible(); await expect(trigger).toBeFocused();
});
test('publishes only after review and explicit consent, then reports a verified saved outcome', async ({ page }) => {
  const api = await controlled(page);
  const { dialog } = await author(page);
  await dialog.getByRole('combobox', { name: 'Save this as', exact: true }).selectOption('published');
  await dialog.getByRole('button', { name: 'Review proposal', exact: true }).click();
  expect(api.calls).toHaveLength(1);
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Confirm and publish', exact: true }).click();
  await expect(dialog.getByText('Your reviewed knowledge was published.', { exact: true })).toBeVisible();
  expect(api.calls[0].body).toMatchObject({ action: 'create_published' });
  expect(api.calls[1].body).toEqual({ confirm: true, expected_revision: 1, authorization_digest: hash, include_remembered_context: true });
  expect(api.calls[1].key).toBeTruthy();
});
test('requires explicit GET status checking for a pending save', async ({ page }) => {
  const api = await controlled(page, 'pending');
  const { dialog } = await author(page);
  await dialog.getByRole('button', { name: 'Review proposal', exact: true }).click();
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Confirm and save draft', exact: true }).click();
  await expect(dialog.getByRole('button', { name: 'Check save status', exact: true })).toBeVisible();
  expect(api.calls).toHaveLength(2);
  await dialog.getByRole('button', { name: 'Check save status', exact: true }).click();
  await expect(dialog.getByText('Your draft was saved. It is not used in retrieval.', { exact: true })).toBeVisible();
  expect(api.calls.at(-1)?.method).toBe('GET');
  expect(api.calls.filter((call) => call.path.endsWith('/confirm'))).toHaveLength(1);
});
test('keeps editable content after a revision conflict and requires a new unchecked review', async ({ page }) => {
  const api = await controlled(page, 'conflict');
  const { dialog } = await author(page);
  await dialog.getByRole('button', { name: 'Review proposal', exact: true }).click();
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Confirm and save draft', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('Review the proposal again before confirming');
  await expect(dialog.getByRole('textbox', { name: 'Knowledge title', exact: true })).toHaveValue('Reviewed renewal rule');
  await expect(dialog.getByRole('textbox', { name: 'Knowledge text', exact: true })).toHaveValue(answer);
  await dialog.getByRole('button', { name: 'Review proposal', exact: true }).click();
  await expect(dialog.getByRole('checkbox')).not.toBeChecked();
  expect(api.calls.filter((call) => call.path.endsWith('/confirm'))).toHaveLength(1);
});

test('preserves the authored proposal after a denied preview', async ({ page }) => {
  const api = await controlled(page, 'denied');
  const { dialog } = await author(page);
  await dialog.getByRole('button', { name: 'Review proposal', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('Check your organization and permissions');
  await expect(dialog.getByRole('textbox', { name: 'Knowledge title', exact: true })).toHaveValue('Reviewed renewal rule');
  await expect(dialog.getByRole('textbox', { name: 'Knowledge text', exact: true })).toHaveValue(answer);
  expect(api.calls).toHaveLength(1);
});
