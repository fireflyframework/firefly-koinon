// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { env, argv } from "node:process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { FetchTransport, KoinonClient } from "@fireflyframework/koinon-sdk";
export function required(name: string): string {
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

export function isMain(url: string): boolean {
  return argv[1] !== undefined && fileURLToPath(url) === resolve(argv[1]);
}
