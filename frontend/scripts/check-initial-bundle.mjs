// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { readFile, stat } from 'node:fs/promises';
import { resolve } from 'node:path';
const targets = process.argv.slice(2);
let failed = false;
for (const target of targets.length ? targets : ['management', 'elements', 'catalog']) {
  const root = resolve('dist', target, 'browser');
  const html = await readFile(resolve(root, 'index.html'), 'utf8');
  const files = new Set();
  for (const tag of html.matchAll(/<(?:script|link)\b[^>]*>/g)) {
    if (!tag[0].startsWith('<script') && !/rel="(?:stylesheet|modulepreload)"/.test(tag[0]))
      continue;
    const path = /(?:src|href)="([^"?#]+)"/.exec(tag[0])?.[1];
    if (path && !/^(?:https?:|\/\/)/.test(path)) files.add(path);
  }
  const bytes = (
    await Promise.all([...files].map(async (file) => (await stat(resolve(root, file))).size))
  ).reduce((sum, size) => sum + size, 0);
  console.log(`${target}: ${bytes} initial bytes (maximum 500000)`);
  if (bytes > 500000) failed = true;
}
if (failed) process.exitCode = 1;
