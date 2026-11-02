// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { initialAssets } from './initial-assets.mjs';
async function fixture(t, files) {
  const root = await mkdtemp(join(tmpdir(), 'koinon-initial-assets-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  for (const [name, content] of Object.entries(files)) {
    const path = join(root, name);
    await mkdir(join(path, '..'), { recursive: true });
    await writeFile(path, content);
  }
  return root;
}
test('counts transitive imports and re-exports once across cycles and preloads, including styles', async (t) => {
  const files = {
    'index.html':
      '<link rel="stylesheet" href="styles.css"><link rel="modulepreload" href="shared.js"><script type="module" src="main.js"></script>',
    'main.js':
      'import "./shared.js"; export { value } from "./barrel.js"; import("./missing-lazy.js");',
    'shared.js': 'import "./barrel.js"; export const shared = 1;',
    'barrel.js': 'import "./shared.js"; export const value = 2;',
    'styles.css': 'body { color: black; }',
  };
  const result = await initialAssets(await fixture(t, files));
  assert.deepEqual(result.files.map((f) => f.path).sort(), [
    'barrel.js',
    'main.js',
    'shared.js',
    'styles.css',
  ]);
  assert.equal(
    result.bytes,
    Buffer.byteLength(
      files['main.js'] + files['shared.js'] + files['barrel.js'] + files['styles.css'],
    ),
  );
});
test('rejects an absent transitive dependency instead of reporting an incomplete size', async (t) => {
  const root = await fixture(t, {
    'index.html': '<script src="main.js"></script>',
    'main.js': 'export * from "./absent.js";',
  });
  await assert.rejects(initialAssets(root), /ENOENT/);
});
test('rejects a local dependency outside the artifact root', async (t) => {
  const root = await fixture(t, {
    'index.html': '<script src="main.js"></script>',
    'main.js': 'import "../outside.js";',
  });
  await assert.rejects(initialAssets(root), /outside.*root/i);
});
test('rejects an empty script inventory rather than passing an unbuilt application', async (t) => {
  const root = await fixture(t, { 'index.html': '<html><body>Not built</body></html>' });
  await assert.rejects(initialAssets(root), /initial script/i);
});
