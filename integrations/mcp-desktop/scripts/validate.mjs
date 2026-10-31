// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

import { spawnSync } from 'node:child_process';
import { lstatSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const manifest = join(root, 'build/manifest.json');

try {
  if (process.argv.length !== 2) throw new Error('Manifest validation does not accept arguments.');
  const metadata = lstatSync(manifest);
  if (!metadata.isFile() || metadata.isSymbolicLink() || metadata.size > 16 * 1024) {
    throw new Error('Generated manifest must be a regular file of at most 16 KiB.');
  }
  // MCPB still requires Zod 3; contain validation of our generated manifest until upstream patches it.
  const result = spawnSync(process.execPath, [
    '--max-old-space-size=128', join(root, 'node_modules/@anthropic-ai/mcpb/dist/cli/cli.js'),
    'validate', manifest,
  ], { cwd: root, encoding: 'utf8', timeout: 15_000, killSignal: 'SIGKILL', maxBuffer: 64 * 1024 });
  if (result.error || result.signal) throw new Error('MCPB validation did not complete within its resource limits.');
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  process.exitCode = result.status ?? 1;
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : 'Manifest validation failed.'}\n`);
  process.exitCode = 1;
}
