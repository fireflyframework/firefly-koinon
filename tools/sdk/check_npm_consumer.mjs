// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import {access, copyFile, mkdir, mkdtemp, readFile, readdir, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const archive = path.resolve(process.argv[2] ?? '');
assert.ok(process.argv[2], 'Pass the built npm archive');
await access(archive);
const sdkCheckDir = await mkdtemp(path.join(tmpdir(), 'koinon-sdk-consumer-'));
const consumer = path.join(sdkCheckDir, 'sdk/typescript');
function run(command, args) {
  const result = spawnSync(command, args, {cwd: consumer, stdio: 'inherit', timeout: 120_000});
  if (result.error) throw result.error;
  assert.equal(result.status, 0, 'Installed SDK consumer check failed');
}
try {
  await mkdir(path.join(consumer, 'test'), {recursive: true});
  await mkdir(path.join(sdkCheckDir, 'sdk/contract'), {recursive: true});
  await copyFile(path.join(repository, 'sdk/contract/operations.json'), path.join(sdkCheckDir, 'sdk/contract/operations.json'));
  await writeFile(path.join(consumer, 'package.json'), JSON.stringify({private: true, type: 'module'}));
  run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['install', '--ignore-scripts', '--no-audit', '--no-fund', archive]);
  const installed = path.join(consumer, 'node_modules/@fireflyframework/koinon-sdk');
  for (const name of ['LICENSE', 'NOTICE']) {
    assert.deepEqual(await readFile(path.join(installed, name)), await readFile(path.join(repository, name)));
  }
  const files = (await readdir(path.join(repository, 'sdk/typescript/test'))).filter(name => name.endsWith('.test.mjs'));
  for (const name of files) {
    const source = await readFile(path.join(repository, 'sdk/typescript/test', name), 'utf8');
    await writeFile(path.join(consumer, 'test', name), source.replaceAll('../dist/index.js', '@fireflyframework/koinon-sdk'));
  }
  run(process.execPath, ['--test', ...files.map(name => path.join('test', name))]);
  console.log('Installed npm archive: contract tests and license notices passed.');
} finally {
  await rm(sdkCheckDir, {recursive: true, force: true});
}
