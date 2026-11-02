// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0

import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { createBridge } from './bridge.js';
import { parseConfig } from './config.js';
declare const KOINON_ICON: string;
declare const KOINON_ICON_DARK: string;

async function main() {
try {
  const server = createBridge(parseConfig(process.env), KOINON_ICON, KOINON_ICON_DARK);
  let closing = false;
  const shutdown = () => {
    if (closing) return;
    closing = true;
    void server.close().finally(() => process.exit(0));
  };
  process.once('SIGINT', shutdown);
  process.once('SIGTERM', shutdown);
  process.stdin.once('end', shutdown);
  process.stdin.once('close', shutdown);
  process.stdin.once('error', shutdown);
  process.stdout.once('error', shutdown);
  await server.connect(new StdioServerTransport());
} catch {
  process.stderr.write('firefly koinon could not start. Configure a valid MCP endpoint and OAuth public client with callback port, or explicitly select pat authentication.\n');
  process.exitCode = 1;
}

}
void main();
