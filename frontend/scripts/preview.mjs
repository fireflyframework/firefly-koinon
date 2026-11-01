// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { createServer, request as proxyRequest } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
const workspace = fileURLToPath(new URL('../', import.meta.url));
const mime = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.json': 'application/json',
  '.woff2': 'font/woff2',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
};
const roots = [
  ['/design/', resolve(workspace, 'dist/catalog/browser')],
  ['/elements/', resolve(workspace, 'dist/elements/browser')],
  ['/sdk/', resolve(workspace, '../sdk/typescript/dist')],
  ['/consumer/', resolve(workspace, 'smoke/angular-host/dist/host/browser')],
  ['/', resolve(workspace, 'dist/management/browser')],
];
createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  if (
    ['/bff', '/auth', '/oauth2', '/login', '/logout'].some(
      (prefix) => url.pathname === prefix || url.pathname.startsWith(prefix + '/'),
    )
  ) {
    const upstream = proxyRequest(
      {
        hostname: '127.0.0.1',
        port: 18781,
        path: req.url,
        method: req.method,
        headers: { ...req.headers, host: '127.0.0.1:18781' },
      },
      (response) => {
        res.writeHead(response.statusCode ?? 502, response.headers);
        response.pipe(res);
      },
    );
    upstream.on('error', () => {
      if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(
        JSON.stringify({ detail: 'The backend is not reachable on the configured local port.' }),
      );
    });
    req.pipe(upstream);
    return;
  }
  const [prefix, root] = roots.find(([prefix]) => url.pathname.startsWith(prefix));
  try {
    const relative = decodeURIComponent(url.pathname.slice(prefix.length));
    let path = resolve(root, relative || 'index.html');
    if (path !== root && !path.startsWith(root + sep)) {
      res.writeHead(403);
      res.end();
      return;
    }
    try {
      if ((await stat(path)).isDirectory()) path = resolve(path, 'index.html');
    } catch {
      path = resolve(root, 'index.html');
    }
    const body = await readFile(path);
    res.writeHead(200, {
      'Content-Type': mime[extname(path)] ?? 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    res.end(body);
  } catch {
    res.writeHead(404);
    res.end('Build this target before starting the preview.');
  }
}).listen(18782, '127.0.0.1', () =>
  process.stdout.write('firefly koinon local preview http://127.0.0.1:18782\n'),
);
