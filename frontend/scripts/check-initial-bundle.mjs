// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { resolve } from 'node:path';
import { initialAssets } from './initial-assets.mjs';
const targets = process.argv.slice(2);
let failed = false;
for (const target of targets.length ? targets : ['management', 'elements', 'catalog']) {
  const result = await initialAssets(resolve('dist', target, 'browser'));
  console.log(`${target}: ${result.bytes} initial bytes (maximum 500000)`);
  if (result.bytes > 500000) failed = true;
}
if (failed) process.exitCode = 1;
