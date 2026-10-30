// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cp, mkdir, mkdtemp, readFile, realpath, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { test, type TestContext } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

async function fixture(t: TestContext) {
  const directory = await realpath(await mkdtemp(join(tmpdir(), 'koinon validation ')));
  t.after(() => rm(directory, { recursive: true, force: true }));
  await mkdir(join(directory, 'scripts'));
  await mkdir(join(directory, 'build'));
  await cp(join(root, 'scripts/validate.mjs'), join(directory, 'scripts/validate.mjs'));
  return directory;
}

function validate(directory: string, args: string[] = []) {
  return spawnSync(process.execPath, [join(directory, 'scripts/validate.mjs'), ...args], {
    encoding: 'utf8', timeout: 20_000, maxBuffer: 128 * 1024,
  });
}

test('oversized, symlinked, and non-file manifests never invoke MCPB', async (t) => {
  for (const kind of ['oversized', 'symlink', 'directory']) {
    const directory = await fixture(t);
    const manifest = join(directory, 'build/manifest.json');
    const cli = join(directory, 'node_modules/@anthropic-ai/mcpb/dist/cli');
    await mkdir(cli, { recursive: true });
    await writeFile(join(cli, 'cli.js'), 'require("node:fs").writeFileSync("invoked", "yes");');
    if (kind === 'oversized') await writeFile(manifest, ' '.repeat(16 * 1024 + 1));
    if (kind === 'directory') await mkdir(manifest);
    if (kind === 'symlink') {
      await writeFile(join(directory, 'target.json'), '{}');
      await symlink(join(directory, 'target.json'), manifest);
    }
    const result = validate(directory);
    assert.ifError(result.error);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /regular file of at most 16 KiB/);
    await assert.rejects(readFile(join(directory, 'invoked')), { code: 'ENOENT' });
  }
});

test('valid preflight preserves validator failure and fixed Node memory arguments', async (t) => {
  const directory = await fixture(t);
  const cli = join(directory, 'node_modules/@anthropic-ai/mcpb/dist/cli');
  await mkdir(cli, { recursive: true });
  await writeFile(join(directory, 'build/manifest.json'), '{}');
  await writeFile(join(cli, 'cli.js'), 'console.log(JSON.stringify({ flags: process.execArgv, args: process.argv.slice(2) })); process.exitCode = 7;');
  const result = validate(directory);
  assert.ifError(result.error);
  assert.equal(result.status, 7);
  assert.deepEqual(JSON.parse(result.stdout), {
    flags: ['--max-old-space-size=128'], args: ['validate', join(directory, 'build/manifest.json')],
  });
  const override = validate(directory, ['other-manifest.json']);
  assert.equal(override.status, 1);
  assert.match(override.stderr, /does not accept arguments/);
});

test('bounded installed MCPB validates the generated manifest and rejects invalid input', async (t) => {
  const valid = validate(root);
  assert.ifError(valid.error);
  assert.equal(valid.status, 0, valid.stdout + valid.stderr);
  assert.match(valid.stdout, /Manifest schema validation passes/);
  const directory = await fixture(t);
  await symlink(join(root, 'node_modules'), join(directory, 'node_modules'), 'junction');
  await writeFile(join(directory, 'build/manifest.json'), '{"manifest_version":"0.3"}');
  const invalid = validate(directory);
  assert.ifError(invalid.error);
  assert.equal(invalid.status, 1);
  assert.match(invalid.stdout, /Manifest validation failed/);
});

test('validator output exceeding the capture limit fails closed', async (t) => {
  const directory = await fixture(t);
  const cli = join(directory, 'node_modules/@anthropic-ai/mcpb/dist/cli');
  await mkdir(cli, { recursive: true });
  await writeFile(join(directory, 'build/manifest.json'), '{}');
  await writeFile(join(cli, 'cli.js'), 'process.stdout.write("x".repeat(128 * 1024));');
  const result = validate(directory);
  assert.ifError(result.error);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /did not complete within its resource limits/);
});
