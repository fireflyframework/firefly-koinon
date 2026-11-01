// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { KoinonTransport } from '../src/index.js';
import { createPlatformHealthApi, type HealthReason, type SystemInformation } from '../src/platform-health.js';
declare const transport: KoinonTransport;
const api = createPlatformHealthApi(transport);
const health = await api.health('tenant', { signal: new AbortController().signal });
const info: SystemInformation = await api.systemInformation('tenant');
const reason: HealthReason | undefined = health.components[0]?.reason;
void reason;
void info.artifacts[0]?.sha256;
// @ts-expect-error No arbitrary user or configuration body is accepted by passive reads.
void api.health('tenant', { subject: 'another-user' });
// @ts-expect-error Reasons are a finite safe wire contract.
const invalid: HealthReason = 'raw-driver-error';
void invalid;
