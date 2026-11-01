// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

import { build } from 'esbuild';
import { readFile, writeFile, mkdir, cp, rm } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repo = resolve(root, '../..');
const out = join(root, 'build');
// This directory contains generated package files only; remove stale entries before assembly.
await rm(out, { recursive: true, force: true });
await mkdir(join(out, 'server'), { recursive: true });
await mkdir(join(out, 'assets'), { recursive: true });
const bundle = await build({
  absWorkingDir: root, entryPoints: ['src/index.ts'], outfile: 'build/server/index.cjs',
  bundle: true, platform: 'node', format: 'cjs', target: 'node22', metafile: true,
  define: {
    KOINON_ICON: JSON.stringify('data:image/png;base64,' + (await readFile(join(repo, 'brand/exports/koinon-symbol-color-128.png'))).toString('base64')),
    KOINON_ICON_DARK: JSON.stringify('data:image/png;base64,' + (await readFile(join(repo, 'brand/exports/koinon-symbol-reversed-128.png'))).toString('base64')),
  },
  banner: { js: '// firefly koinon — Copyright 2026 Firefly Software Foundation. Apache-2.0. See LICENSE and THIRD_PARTY_NOTICES.txt.' },
});
for (const [source, target] of [
  ['brand/exports/koinon-symbol-color-512.png', 'icon.png'],
  ['brand/exports/koinon-symbol-reversed-512.png', 'icon-dark.png'],
  ['brand/logos/firefly-koinon-lockup-color.svg', 'lockup.svg'],
  ['brand/logos/firefly-koinon-lockup-reversed.svg', 'lockup-dark.svg'],
  ['docs/assets/fonts/manrope-latin-wght-normal.woff2', 'manrope.woff2'],
  ['docs/assets/OFL.txt', 'FONT-LICENSE.txt'],
]) await cp(join(repo, source), join(out, 'assets', target));
for (const name of ['manifest.json', 'README.md', 'preview.html', 'NOTICE']) await cp(join(root, name), join(out, name));
for (const name of ['LICENSE']) await cp(join(repo, name), join(out, name));
await cp(join(root, 'skills'), join(out, 'skills'), { recursive: true });
const lock = JSON.parse(await readFile(join(root, 'package-lock.json'), 'utf8'));
const dependencies = new Map();
for (const input of Object.keys(bundle.metafile.inputs).sort()) {
  if (!input.startsWith('node_modules/')) continue;
  const segments = input.split('/');
  const length = segments[1].startsWith('@') ? 3 : 2;
  const packagePath = segments.slice(0, length).join('/');
  if (dependencies.has(packagePath)) continue;
  const metadata = JSON.parse(await readFile(join(root, packagePath, 'package.json'), 'utf8'));
  const entry = lock.packages[packagePath];
  if (!entry || entry.version !== metadata.version ||
      typeof entry.resolved !== 'string' || !entry.resolved.trim() ||
      typeof entry.integrity !== 'string' || !entry.integrity.trim()) {
    throw new Error(`Missing or inconsistent lock provenance for ${metadata.name}`);
  }
  let licenseText = '';
  for (const name of ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'license', 'LICENSE-MIT', 'COPYING']) {
    try { licenseText = await readFile(join(root, packagePath, name), 'utf8'); break; } catch {}
  }
  if (!licenseText) throw new Error(`Missing license text for ${metadata.name}`);
  dependencies.set(packagePath, { name: metadata.name, version: metadata.version, license: metadata.license, resolved: entry.resolved, integrity: entry.integrity, licenseText });
}
const provenance = [...dependencies.values()].sort((a, b) => a.name.localeCompare(b.name));
await writeFile(join(out, 'DEPENDENCIES.json'), JSON.stringify(provenance.map(({ licenseText, ...metadata }) => metadata), null, 2) + '\n');
await writeFile(join(out, 'THIRD_PARTY_NOTICES.txt'), provenance.map((entry) => `${entry.name} ${entry.version}\n${entry.license}\n\n${entry.licenseText}`).join('\n\n' + '='.repeat(72) + '\n\n'));
await writeFile(join(out, 'package.json'), JSON.stringify({ name: '@fireflyframework/koinon-mcp-desktop-bundle', version: '26.11.4', license: 'Apache-2.0', private: true }, null, 2) + '\n');
console.log(`Built relocatable bridge with ${provenance.length} bundled dependencies and license notices.`);
