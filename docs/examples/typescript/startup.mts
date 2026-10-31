// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { isMain } from "./support.mjs";
import { env } from "node:process";
import {
  FetchTransport,
  KoinonClient,
  offsetPages,
} from "@fireflyframework/koinon-sdk";
function required(name: string): string {
  const value = env[name];
  if (!value) throw new Error(`Set ${name} before running this example`);
  return value;
}

export function connect(): KoinonClient {
  return new KoinonClient({
    transport: new FetchTransport({
      baseUrl: required("KOINON_API_URL"),
      accessToken: () => required("KOINON_TOKEN"),
      credentials: "omit",
    }),
  });
}

export async function browse(client: KoinonClient, tenant: string, workspace: string) {
  for await (const page of offsetPages((number) =>
    client.catalog.list(tenant, {
      workspace_id: workspace,
      kind: "document",
      page: number,
      page_size: 25,
      sort: "name",
      order: "asc",
    }),
  )) {
    for (const document of page.items) console.log(document.id, document.name);
  }
}

async function main() {
  const client = connect();
  const tenant = required("KOINON_TENANT_ID");
  const context = await client.context();
  if (!context.tenants.some((item) => item.id === tenant)) {
    throw new Error("The selected organization is unavailable");
  }
  await browse(client, tenant, required("KOINON_WORKSPACE_ID"));
}

if (isMain(import.meta.url)) await main();
