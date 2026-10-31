// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled MCP Apps protocol host; this does not qualify a hosted chat client.
import { test, expect, type Page } from '@playwright/test';
import { readFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
const assets = resolve(__dirname, '../../backend/src/koinon/mcp/assets');
const output = resolve(__dirname, '../../../../outputs/mcp-review');
const review = {
  id: 'review-one',
  status: 'preview',
  expires_at: '2099-01-01T00:00:00Z',
  review: {
    id: 'review-one',
    revision: 1,
    tenant_id: 'north',
    action: 'create_published',
    target_item_id: 'knowledge-one',
    authorization_digest: 'a'.repeat(64),
    status: 'preview',
    before: null,
    after: {
      title: 'Service ownership',
      body: 'The operations lead reviews service ownership every quarter.',
      summary: null,
      tags: ['operations'],
    },
    destination: {
      id: 'collection-one',
      name: 'Policies',
      workspace_id: 'workspace-one',
      project_id: 'project-one',
    },
    evidence: [
      { kind: 'external_proposal', authority: 'external_unverified', provider: null, model: null },
    ],
    receipt: null,
  },
};
async function open(
  page: Page,
  options: {
    handshake?: boolean;
    denied?: boolean;
    body?: string;
    expires?: string;
    theme?: 'light' | 'dark';
    privateChannel?: boolean;
    pendingApprove?: boolean;
    wrongOperation?: boolean;
    presentation?: Record<string, unknown>;
  } = {},
) {
  const template = await readFile(resolve(assets, 'review.html'), 'utf8');
  const html = template
    .replace('/*__KOINON_REVIEW_CSS__*/', await readFile(resolve(assets, 'review.css'), 'utf8'))
    .replace(
      '/*__KOINON_REVIEW_SCRIPT__*/',
      (await readFile(resolve(assets, 'review-file.js'), 'utf8')) +
        '\n' +
        (await readFile(resolve(assets, 'review.js'), 'utf8')),
    )
    .replace(
      '__KOINON_FONT_BASE64__',
      (await readFile(resolve(assets, '../../mcp_auth/assets/manrope.woff2'))).toString('base64'),
    )
    .replace(
      '__KOINON_INTER_FONT_BASE64__',
      (await readFile(resolve(assets, '../../organization_branding/assets/inter.woff2'))).toString(
        'base64',
      ),
    );
  await page.route('**/controlled-mcp-review', (r) =>
    r.fulfill({ contentType: 'text/html', body: html }),
  );
  const value = structuredClone(review);
  if (options.body) value.review.after.body = options.body;
  if (options.expires) value.expires_at = options.expires;
  const data = JSON.stringify(value).replaceAll('<', '\\u003c');
  await page.route('**/controlled-mcp-host', (r) =>
    r.fulfill({
      contentType: 'text/html',
      body: `<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;font:14px sans-serif;background:#f3f1eb"><p style="padding:12px">Review in a controlled MCP Apps host.</p><iframe title="Knowledge review" src="/controlled-mcp-review" style="border:0;width:100%;height:1000px"></iframe><script>
  const review=${data};window.calls=[];window.addEventListener('message',e=>{
   if(e.source!==document.querySelector('iframe').contentWindow)return;const m=e.data;
   const reply=result=>e.source.postMessage({jsonrpc:'2.0',id:m.id,result},'*');
   if(m.method==='ui/initialize' && ${options.handshake !== false}){reply({protocolVersion:'2026-01-26',hostInfo:{name:'Controlled host',version:'1'},hostCapabilities:{serverTools:{}},hostContext:{theme:'${options.theme ?? 'light'}'}});}
   if(m.method==='ui/notifications/initialized'){e.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-input',params:{arguments:{tenant_id:'north'}}},'*');e.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:{review},_meta:${options.privateChannel === false ? '{}' : "{'koinon/knowledgeReview':{review,nonce:'controlled-private-challenge',presentation:" + JSON.stringify(options.presentation ?? {}).replaceAll('<', '\\u003c') + '}}'}}},'*');}
   if(m.method==='tools/call'){window.calls.push(m.params);if(${options.denied === true}){reply({isError:true,content:[{type:'text',text:'Canonical request denied (403, ACCESS_DENIED)'}]});return;}
    const receipt={operation_id:review.id,intent_id:review.id,intent_revision:review.review.revision,authorization_digest:review.review.authorization_digest,item_id:'knowledge-one',native_item_id:'native-one',native_version_id:'native-version-one',version:1,serving_version:null,action:review.review.action,content_sha256:'b'.repeat(64),evidence_sha256:'c'.repeat(64),committed_at:'2026-10-29T10:00:00Z',retrieval_state:'lexical_ready',reason:null};
    if(${options.wrongOperation === true})receipt.operation_id='other-operation';
    if(m.params.name==='koinon_cancel_knowledge'){review.status='cancelled';reply({structuredContent:review,content:[{type:'text',text:'Recorded'}]});return;}
    if(m.params.name==='koinon_approve_knowledge' && ${options.pendingApprove === true}){review.status='unresolved';reply({structuredContent:{status:'pending',operation_id:${JSON.stringify(options.wrongOperation === true ? 'other-operation' : review.id)},intent_id:review.id,reason:'commit_outcome_unresolved'},content:[{type:'text',text:'Recorded'}]});return;}
    review.status='committed';review.review.receipt=receipt;
    reply({structuredContent:m.params.name==='koinon_approve_knowledge'?{status:'committed',receipt}:{review},content:[{type:'text',text:'Recorded'}]});}
  });</script></body></html>`,
    }),
  );
  await page.goto('/controlled-mcp-host');
  return page.frameLocator('iframe');
}
test('requires an explicit in-chat approval and sends the exact private challenge once', async ({
  page,
}) => {
  await page.setViewportSize({ width: 900, height: 1100 });
  const app = await open(page);
  await expect(app.getByRole('heading', { name: 'Service ownership', exact: true })).toBeVisible();
  const approve = app.getByRole('button', { name: 'Approve & save', exact: true });
  await expect(approve).toBeDisabled();
  await expect(app.locator('body')).not.toContainText('controlled-private-challenge');
  await app.getByRole('checkbox', { name: /I approve this exact change/ }).check();
  await mkdir(output, { recursive: true });
  await page.screenshot({ path: resolve(output, 'knowledge-review-desktop.png') });
  await approve.click();
  await expect(app.getByRole('status')).toContainText('Knowledge saved');
  const calls = await page.evaluate(() => Reflect.get(window, 'calls'));
  expect(calls).toHaveLength(1);
  expect(calls[0]).toMatchObject({
    name: 'koinon_approve_knowledge',
    arguments: {
      tenant_id: 'north',
      review_id: 'review-one',
      expected_revision: 1,
      authorization_digest: 'a'.repeat(64),
      nonce: 'controlled-private-challenge',
    },
  });
  expect(calls[0].arguments.idempotency_key).toMatch(/^[a-f0-9-]{36}$/);
  await expect(approve).toBeDisabled();
});
test('unsupported hosts cannot approve and never redirect to another site', async ({ page }) => {
  const app = await open(page, { handshake: false });
  await expect(app.getByRole('alert')).toContainText('does not support');
  await expect(app.locator('#approve')).toBeDisabled();
  await expect(app.locator('#approve')).toBeHidden();
  expect(await page.evaluate(() => Reflect.get(window, 'calls'))).toEqual([]);
  expect(page.url()).toContain('/controlled-mcp-host');
});
test('renders model content as text and keeps denied changes unsaved on mobile', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const app = await open(page, {
    denied: true,
    body: '<img src=x onerror="window.untrustedRan=true">',
  });
  await expect(
    app.getByText('<img src=x onerror="window.untrustedRan=true">', { exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => Reflect.get(window, 'untrustedRan'))).toBeUndefined();
  await app.getByRole('checkbox', { name: /I approve this exact change/ }).check();
  await app.getByRole('button', { name: 'Approve & save', exact: true }).click();
  await expect(app.getByRole('alert')).toContainText('could not be saved');
  expect(await app.locator('body').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
  await mkdir(output, { recursive: true });
  await page.screenshot({ path: resolve(output, 'knowledge-review-mobile-denied.png') });
});

test('requires a new decision when the proposed revision changes', async ({ page }) => {
  const app = await open(page);
  const approve = app.getByRole('button', { name: 'Approve & save', exact: true });
  await app.getByRole('checkbox', { name: /I approve this exact change/ }).check();
  await expect(approve).toBeEnabled();
  const changed = structuredClone(review);
  changed.review.revision = 2;
  changed.review.authorization_digest = 'd'.repeat(64);
  changed.review.after.body = 'A different reviewed change.';
  await page.evaluate(
    (value) =>
      document.querySelector('iframe')!.contentWindow!.postMessage(
        {
          jsonrpc: '2.0',
          method: 'ui/notifications/tool-result',
          params: {
            structuredContent: { review: value },
            _meta: {
              'koinon/knowledgeReview': { review: value, nonce: 'fresh-private-challenge' },
            },
          },
        },
        '*',
      ),
    changed,
  );
  await expect(app.getByText('A different reviewed change.', { exact: true })).toBeVisible();
  await expect(approve).toBeDisabled();
  await expect(
    app.getByRole('checkbox', { name: /I approve this exact change/ }),
  ).not.toBeChecked();
});
test('never enables approval for an expired review', async ({ page }) => {
  const app = await open(page, { expires: '2000-01-01T00:00:00Z' });
  await expect(app.getByRole('heading', { name: 'Service ownership', exact: true })).toBeVisible();
  await expect(app.getByRole('checkbox', { name: /I approve this exact change/ })).toBeDisabled();
  await expect(app.getByRole('button', { name: 'Approve & save', exact: true })).toBeDisabled();
});

test('uses the chat host dark appearance and a loaded local Manrope font', async ({ page }) => {
  const app = await open(page, { theme: 'dark' });
  await expect(app.getByRole('heading', { name: 'Service ownership', exact: true })).toBeVisible();
  await expect(app.locator('body')).toHaveCSS('background-color', 'rgb(29, 31, 26)');
  expect(
    await app.locator('body').evaluate(async () => {
      await document.fonts.ready;
      return [...document.fonts].some(
        (face) => face.family === 'Manrope' && face.status === 'loaded',
      );
    }),
  ).toBe(true);
});
test('missing private review metadata shows a clear capability error and cannot approve', async ({
  page,
}) => {
  const app = await open(page, { privateChannel: false });
  await expect(app.getByRole('alert')).toContainText('private approval channel');
  await expect(app.locator('#approve')).toBeDisabled();
  expect(await page.evaluate(() => Reflect.get(window, 'calls'))).toEqual([]);
});

test('cancel accepts the canonical plain review response without an uncertain save message', async ({
  page,
}) => {
  const app = await open(page);
  await app.getByRole('button', { name: 'Cancel change', exact: true }).click();
  await expect(app.getByRole('status')).toHaveText('Change cancelled. No knowledge was saved.');
  await expect(app.getByRole('alert')).toBeHidden();
});
test('pending canonical commit is reconciled by status without replaying approval', async ({
  page,
}) => {
  const app = await open(page, { pendingApprove: true });
  await app.getByRole('checkbox', { name: /I approve this exact change/ }).check();
  await app.getByRole('button', { name: 'Approve & save', exact: true }).click();
  await expect(app.getByRole('status')).toContainText('outcome needs to be checked');
  await expect(app.getByRole('button', { name: 'Approve & save', exact: true })).toBeDisabled();
  await app.getByRole('button', { name: 'Check status', exact: true }).click();
  await expect(app.getByRole('status')).toContainText('Knowledge saved. Version 1.');
  const calls = await page.evaluate(() => Reflect.get(window, 'calls'));
  expect(calls.map((c: { name: string }) => c.name)).toEqual([
    'koinon_approve_knowledge',
    'koinon_review_status',
  ]);
});
test('a late file response cannot replace the text review bound to this component', async ({
  page,
}) => {
  const app = await open(page);
  await expect(app.getByRole('heading', { name: 'Service ownership', exact: true })).toBeVisible();
  await page.evaluate(() =>
    document.querySelector('iframe')!.contentWindow!.postMessage(
      {
        jsonrpc: '2.0',
        method: 'ui/notifications/tool-result',
        params: {
          structuredContent: {
            kind: 'file_upload',
            setup: {
              tenant_id: 'north',
              destination_id: 'other',
              destination_name: 'Other',
              mode: 'dataset',
              max_file_bytes: 33554432,
              chunk_bytes: 65536,
            },
          },
        },
      },
      '*',
    ),
  );
  await expect(app.getByRole('heading', { name: 'Service ownership', exact: true })).toBeVisible();
  await expect(app.locator('#file-content')).toBeHidden();
});

for (const pendingApprove of [false, true])
  test(`a mismatched ${pendingApprove ? 'pending' : 'committed'} operation cannot be shown as this review outcome`, async ({
    page,
  }) => {
    const app = await open(page, { pendingApprove, wrongOperation: true });
    await app.getByRole('checkbox', { name: /I approve this exact change/ }).check();
    await app.getByRole('button', { name: 'Approve & save', exact: true }).click();
    await expect(app.getByRole('alert')).toContainText('could not be saved or confirmed');
    await expect(app.locator('#message')).not.toContainText('Knowledge saved');
    expect(
      (await page.evaluate(() => Reflect.get(window, 'calls'))).filter(
        (call: { name: string }) => call.name === 'koinon_approve_knowledge',
      ),
    ).toHaveLength(1);
  });

test('authorized review presentation loads the bundled Inter face without changing host typography', async ({
  page,
}) => {
  const app = await open(page, {
    presentation: { product_name: 'North <Knowledge>', font_family: 'Inter' },
  });
  await expect(app.locator('#product-name')).toHaveText('North <Knowledge>');
  await expect(app.getByRole('heading', { name: 'Service ownership', exact: true })).toBeVisible();
  await expect
    .poll(() => app.locator('body').evaluate((node) => getComputedStyle(node).fontFamily))
    .toContain('Inter');
  await expect
    .poll(() =>
      app.locator('body').evaluate(async () => {
        await document.fonts.ready;
        return Array.from(document.fonts).some(
          (face) => face.family === 'Inter' && face.status === 'loaded',
        );
      }),
    )
    .toBe(true);
  const encoded = (
    await readFile(resolve(assets, '../../organization_branding/assets/inter.woff2'))
  ).toString('base64');
  expect(await app.locator('style').textContent()).toContain('data:font/woff2;base64,' + encoded);
  expect(await app.locator('script[src]').count()).toBe(0);
  expect(await page.locator('body').evaluate((node) => getComputedStyle(node).fontFamily)).toBe(
    'sans-serif',
  );
  expect(await app.locator('#product-name script').count()).toBe(0);
  await expect(app.getByRole('button', { name: 'Approve & save', exact: true })).toBeDisabled();
});

test('review presentation rejects a CSS font payload while preserving explicit approval', async ({
  page,
}) => {
  const app = await open(page, {
    presentation: { font_family: 'Inter; background:url(https://invalid.example/font)' },
  });
  await expect(app.getByRole('heading', { name: 'Service ownership', exact: true })).toBeVisible();
  expect(await app.locator('body').evaluate((node) => getComputedStyle(node).fontFamily)).toContain(
    'Manrope',
  );
  expect(await app.locator('html').getAttribute('style')).not.toContain('invalid.example');
  await expect(app.getByRole('button', { name: 'Approve & save', exact: true })).toBeDisabled();
});
