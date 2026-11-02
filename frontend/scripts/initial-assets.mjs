// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { readFile, realpath, stat } from 'node:fs/promises';
import { dirname, relative, resolve, sep } from 'node:path';
import ts from 'typescript';
export async function initialAssets(directory) {
  const root = await realpath(directory);
  const inside = (path) => path === root || path.startsWith(root + sep);
  const pending = [],
    seen = new Set(),
    files = [];
  async function local(base, reference) {
    const name = decodeURIComponent(reference.split(/[?#]/)[0]);
    const candidate = name.startsWith('/') ? resolve(root, '.' + name) : resolve(base, name);
    if (!inside(candidate)) throw Error('Initial asset is outside the artifact root');
    const path = await realpath(candidate);
    if (!inside(path)) throw Error('Initial asset resolves outside the artifact root');
    return path;
  }
  const html = await readFile(resolve(root, 'index.html'), 'utf8');
  let scripts = 0;
  for (const tag of html.matchAll(/<(?:script|link)\b[^>]*>/g)) {
    const script = tag[0].startsWith('<script');
    if (!script && !/rel="(?:stylesheet|modulepreload)"/.test(tag[0])) continue;
    const reference = /(?:src|href)="([^"?#]+)"/.exec(tag[0])?.[1];
    if (!reference || /^(?:https?:|\/\/)/.test(reference)) continue;
    pending.push(await local(root, reference));
    if (script) ++scripts;
  }
  if (!scripts) throw Error('An initial script inventory is required');
  while (pending.length) {
    const path = pending.pop();
    if (seen.has(path)) continue;
    seen.add(path);
    const info = await stat(path);
    if (!info.isFile()) throw Error('Initial asset is not a regular file');
    files.push({ path: relative(root, path), size: info.size });
    if (!/\.m?js$/.test(path)) continue;
    const source = ts.createSourceFile(
      path,
      await readFile(path, 'utf8'),
      ts.ScriptTarget.ESNext,
      false,
      ts.ScriptKind.JS,
    );
    if (source.parseDiagnostics.length) throw Error('An initial module could not be parsed');
    for (const statement of source.statements) {
      if (
        !(ts.isImportDeclaration(statement) || ts.isExportDeclaration(statement)) ||
        !statement.moduleSpecifier ||
        !ts.isStringLiteral(statement.moduleSpecifier)
      )
        continue;
      const reference = statement.moduleSpecifier.text;
      if (!reference.startsWith('.') && !reference.startsWith('/'))
        throw Error('An initial module has an unbundled dependency');
      pending.push(await local(dirname(path), reference));
    }
  }
  files.sort((a, b) => a.path.localeCompare(b.path));
  return { files, bytes: files.reduce((total, file) => total + file.size, 0) };
}
