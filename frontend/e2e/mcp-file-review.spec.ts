// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// Controlled MCP Apps file transport. Native storage/ingestion has separate acceptance tests.
import { test, expect } from '@playwright/test';
import { readFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
async function open(
  page: import('@playwright/test').Page,
  options: { denyApprove?: boolean; chunkDelay?: number } = {},
) {
  const assets = resolve(__dirname, '../../backend/src/koinon/mcp/assets');
  let html = await readFile(resolve(assets, 'review.html'), 'utf8');
  html = html
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
    );
  await page.route('**/controlled-file-widget', (r) =>
    r.fulfill({ contentType: 'text/html', body: html }),
  );
  await page.route('**/controlled-file-host', (r) =>
    r.fulfill({
      contentType: 'text/html',
      body: `<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;font:13px sans-serif;background:#f3f1eb"><p style="padding:12px">File review in a controlled MCP Apps host.</p><iframe title="File review" src="/controlled-file-widget" style="border:0;width:100%;height:1100px"></iframe><script>
 const setup={tenant_id:'north',destination_id:'collection-one',destination_name:'Policies',mode:'dataset',max_file_bytes:33554432,chunk_bytes:65536};
 window.calls=[];const chunks=new Map();let review=null;
 const hash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
 addEventListener('message',async e=>{if(e.source!==document.querySelector('iframe').contentWindow)return;const m=e.data;const reply=value=>e.source.postMessage({jsonrpc:'2.0',id:m.id,result:value},'*');
 if(m.method==='ui/initialize')reply({protocolVersion:'2026-01-26',hostCapabilities:{serverTools:{}},hostInfo:{name:'Controlled host',version:'1'}});
 if(m.method==='ui/notifications/initialized')e.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:{kind:'file_upload',setup},_meta:{'koinon/knowledgeReview':{kind:'file_upload',setup}}}},'*');
 if(m.method==='tools/call'){window.calls.push(m.params);const a=m.params.arguments;
 if(m.params.name==='koinon_stage_file')review={id:'file-review-one',tenant_id:'north',revision:1,status:'uploading',authorization_digest:'a'.repeat(64),...a.file,destination:{id:'collection-one',name:'Policies',workspace_id:'workspace-one',project_id:'project-one'},received_chunks:0,total_chunks:Math.ceil(a.file.size_bytes/65536),expires_at:'2099-01-01T00:00:00Z',submitted_by:'example-user',credential_id:'credential-one',application_id:null,origin:'external_proposal',authority:'unverified',provider:null,model:null,receipt:null};
 if(m.params.name==='koinon_upload_file_chunk'){await new Promise(done=>setTimeout(done,${options.chunkDelay ?? 0}));const b=Uint8Array.from(atob(a.chunk.data_base64),c=>c.charCodeAt(0));if(await hash(b)!==a.chunk.sha256)throw Error('Bad chunk');chunks.set(a.chunk.index,b);review.received_chunks=chunks.size;}
 if(m.params.name==='koinon_seal_file'){const b=new Uint8Array(review.size_bytes);for(const [i,data]of chunks)b.set(data,i*65536);if(await hash(b)!==review.sha256)throw Error('Bad full hash');window.fileBytes=Array.from(b);review.status='preview';review.revision=2;}
 if(m.params.name==='koinon_approve_file'){if(${options.denyApprove === true}){reply({isError:true,content:[{type:'text',text:'Denied'}]});return;}if(a.nonce!=='n'.repeat(43))throw Error('Wrong nonce');review.status='committed';review.receipt={source:{id:'source-one',name:review.filename},assets:[{id:'dataset-one',name:review.filename,kind:'dataset'}]};}
 if(m.params.name==='koinon_cancel_file')review.status='cancelled';
 reply({structuredContent:{kind:'file',review},_meta:{'koinon/knowledgeReview':{kind:'file',review,nonce:'n'.repeat(43)}}});}
 });</script></body></html>`,
    }),
  );
  await page.goto('/controlled-file-host');
  return page.frameLocator('iframe');
}
for (const width of [900, 390])
  test(`file bytes are staged and reviewed before explicit in-chat ingestion at ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1100 });
    const app = await open(page);
    const bytes = Buffer.from('team,records\nOperations,24\n');
    await app
      .getByLabel('Choose a file', { exact: true })
      .setInputFiles({ name: 'team-records.csv', mimeType: 'text/csv', buffer: bytes });
    await app.getByRole('button', { name: 'Upload for review', exact: true }).click();
    await expect(app.getByRole('button', { name: 'Approve & import', exact: true })).toBeDisabled();
    await expect(app.getByText('Ready for your approval', { exact: true })).toBeVisible();
    await expect(app.getByText('text/csv', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => Reflect.get(window, 'fileBytes'))).toEqual([...bytes]);
    expect(
      (await page.evaluate(() => Reflect.get(window, 'calls'))).some(
        (call: { name: string }) => call.name === 'koinon_approve_file',
      ),
    ).toBe(false);
    await app.getByRole('checkbox', { name: /I approve importing this exact file/ }).check();
    const out = resolve(__dirname, '../../../../outputs/mcp-review');
    await mkdir(out, { recursive: true });
    await page.screenshot({ path: resolve(out, `file-review-${width}.png`) });
    await app.getByRole('button', { name: 'Approve & import', exact: true }).click();
    await expect(app.getByText('File imported. Source: source-one', { exact: true })).toBeVisible();
    expect(await app.locator('body').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
  });

test('denied file approval stays visible and does not retry ingestion', async ({ page }) => {
  const app = await open(page, { denyApprove: true });
  await app
    .getByLabel('Choose a file', { exact: true })
    .setInputFiles({ name: 'records.csv', mimeType: 'text/csv', buffer: Buffer.from('id\n1\n') });
  await app.getByRole('button', { name: 'Upload for review', exact: true }).click();
  await expect(app.getByText('Ready for your approval', { exact: true })).toBeVisible();
  await app.getByRole('checkbox', { name: /I approve importing this exact file/ }).check();
  await app.getByRole('button', { name: 'Approve & import', exact: true }).click();
  await expect(app.getByRole('alert')).toContainText('could not be confirmed');
  await expect(app.getByRole('button', { name: 'Approve & import', exact: true })).toBeDisabled();
  expect(
    (await page.evaluate(() => Reflect.get(window, 'calls'))).filter(
      (c: { name: string }) => c.name === 'koinon_approve_file',
    ),
  ).toHaveLength(1);
});
test('cancelling an active upload finishes outstanding chunks and closes the staged file', async ({
  page,
}) => {
  const app = await open(page, { chunkDelay: 150 });
  await app.getByLabel('Choose a file', { exact: true }).setInputFiles({
    name: 'records.csv',
    mimeType: 'text/csv',
    buffer: Buffer.alloc(5 * 65536, 65),
  });
  await app.getByRole('button', { name: 'Upload for review', exact: true }).click();
  await expect
    .poll(() =>
      page.evaluate(() =>
        Reflect.get(window, 'calls').some(
          (c: { name: string }) => c.name === 'koinon_upload_file_chunk',
        ),
      ),
    )
    .toBe(true);
  await app.getByRole('button', { name: 'Cancel upload', exact: true }).click();
  await expect(
    app.getByText('Upload cancelled. No knowledge was imported.', { exact: true }),
  ).toBeVisible();
  expect(
    (await page.evaluate(() => Reflect.get(window, 'calls'))).some(
      (c: { name: string }) => c.name === 'koinon_approve_file',
    ),
  ).toBe(false);
});

test('a file review rejects a late text review instead of mixing approval controls', async ({
  page,
}) => {
  const app = await open(page);
  await expect(app.getByRole('heading', { name: 'Upload knowledge', exact: true })).toBeVisible();
  await page.evaluate(() =>
    document.querySelector('iframe')!.contentWindow!.postMessage(
      {
        jsonrpc: '2.0',
        method: 'ui/notifications/tool-result',
        params: {
          structuredContent: {
            review: {
              id: 'text-b',
              status: 'preview',
              expires_at: '2099-01-01T00:00:00Z',
              review: {
                id: 'text-b',
                tenant_id: 'north',
                revision: 1,
                authorization_digest: 'b'.repeat(64),
                action: 'create_published',
                target_item_id: 'knowledge-two',
                destination: { id: 'other', name: 'Other' },
                before: null,
                after: { title: 'Unrelated text', body: 'Different change' },
                evidence: [],
              },
            },
          },
          _meta: { 'koinon/knowledgeReview': { nonce: 'other-nonce' } },
        },
      },
      '*',
    ),
  );
  await expect(app.getByRole('heading', { name: 'Upload knowledge', exact: true })).toBeVisible();
  await expect(app.locator('#review-content')).toBeHidden();
});
