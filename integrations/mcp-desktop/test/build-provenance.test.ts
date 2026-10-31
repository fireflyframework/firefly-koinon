// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cp, mkdir, mkdtemp, readFile, realpath, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

test('actual builds reject stale installed versions and incomplete lock provenance', async (t) => {
  const repo = await realpath(await mkdtemp(join(tmpdir(), 'koinon provenance ')));
  t.after(() => rm(repo, { recursive: true, force: true }));
  const directory = join(repo, 'integrations/mcp-desktop');
  await mkdir(directory, { recursive: true });
  for (const name of ['scripts', 'src', 'skills', 'node_modules', 'package.json', 'package-lock.json', 'manifest.json', 'README.md', 'preview.html', 'NOTICE', 'tsconfig.json']) {
    await cp(join(root, name), join(directory, name), { recursive: true });
  }
  for (const name of ['brand', 'docs', 'LICENSE']) {
    await symlink(resolve(root, '../..', name), join(repo, name), name === 'LICENSE' ? 'file' : 'junction');
  }
  const metadataPath = join(directory, 'node_modules/zod/package.json');
  const lockPath = join(directory, 'package-lock.json');
  const originalMetadata = await readFile(metadataPath, 'utf8');
  const originalLock = await readFile(lockPath, 'utf8');
  const build = () => spawnSync(process.execPath, ['scripts/build.mjs'], {
    cwd: directory, encoding: 'utf8', timeout: 30_000, maxBuffer: 128 * 1024,
  });
  for (const kind of ['stale-version', 'missing-entry', 'missing-resolved', 'missing-integrity', 'empty-resolved', 'empty-integrity']) {
    await writeFile(metadataPath, originalMetadata);
    await writeFile(lockPath, originalLock);
    if (kind === 'stale-version') {
      const metadata = JSON.parse(originalMetadata);
      metadata.version = '3.25.76';
      await writeFile(metadataPath, JSON.stringify(metadata));
    } else {
      const lock = JSON.parse(originalLock);
      if (kind === 'missing-entry') delete lock.packages['node_modules/zod'];
      else {
        const field = kind.endsWith('resolved') ? 'resolved' : 'integrity';
        if (kind.startsWith('missing-')) delete lock.packages['node_modules/zod'][field];
        else lock.packages['node_modules/zod'][field] = ' ';
      }
      await writeFile(lockPath, JSON.stringify(lock));
    }
    const result = build();
    assert.ifError(result.error);
    assert.notEqual(result.status, 0, `${kind}: build accepted inconsistent provenance`);
    assert.match(result.stderr, /Missing or inconsistent lock provenance for zod/);
    await assert.rejects(readFile(join(directory, 'build/DEPENDENCIES.json')), { code: 'ENOENT' });
  }
  await writeFile(metadataPath, originalMetadata);
  await writeFile(lockPath, originalLock);
  const clean = build();
  assert.ifError(clean.error);
  assert.equal(clean.status, 0, clean.stdout + clean.stderr);
  const provenance = JSON.parse(await readFile(join(directory, 'build/DEPENDENCIES.json'), 'utf8'));
  const zod = provenance.find((entry: { name: string }) => entry.name === 'zod');
  assert.equal(zod.version, '4.6.6');
  assert.deepEqual(zod, {
    name: 'zod', version: '4.6.6', license: 'MIT',
    resolved: JSON.parse(originalLock).packages['node_modules/zod'].resolved,
    integrity: JSON.parse(originalLock).packages['node_modules/zod'].integrity,
  });
});
