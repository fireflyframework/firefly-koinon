// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { KoinonTransport, RequestOptions } from "./transport.js";
import type { HealthComponent, PlatformHealth, SystemInformation } from "./generated.js";
export type {
  HealthComponent, HealthCounts, HealthSummary, PlatformHealth, SystemInformation,
  SystemComponentVersion, SystemCapabilities, SystemLimit, SystemArtifact,
} from "./generated.js";
export type HealthStatus = HealthComponent["status"];
export type HealthComponentId = HealthComponent["id"];
export type HealthBasis = HealthComponent["basis"];
export type HealthFreshness = HealthComponent["freshness"];
export type HealthCoverage = HealthComponent["coverage"];
export type HealthReason = HealthComponent["reason"];
export type HealthRemediation = HealthComponent["remediation"];

/** Passive organization-wide observations; current administrator authority remains server-enforced. */
export function createPlatformHealthApi(transport: KoinonTransport) {
  return {
    health: (tenantId: string, options: RequestOptions = {}) =>
      transport.request<PlatformHealth>("GET", `/tenants/${encodeURIComponent(tenantId)}/platform/health`, options),
    systemInformation: (tenantId: string, options: RequestOptions = {}) =>
      transport.request<SystemInformation>("GET", `/tenants/${encodeURIComponent(tenantId)}/platform/system-information`, options),
  };
}
