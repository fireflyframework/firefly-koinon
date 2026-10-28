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
  const shutdown = () => { void server.close().finally(() => process.exit(0)); };
  process.once('SIGINT', shutdown);
  process.once('SIGTERM', shutdown);
  await server.connect(new StdioServerTransport());
} catch {
  process.stderr.write('firefly koinon could not start. Configure a valid MCP endpoint and personal access token.\n');
  process.exitCode = 1;
}

}
void main();
