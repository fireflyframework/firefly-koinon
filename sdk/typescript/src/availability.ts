// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { KoinonTransport, RequestOptions } from "./transport.js";
import type {
  AvailabilityRequest,
  AvailabilityResponse,
  ProcessingRequest,
  ProcessingResponse,
} from "./generated.js";
export type {
  AssetAvailability,
  AvailabilityRequest,
  AvailabilityResponse,
  ProcessingRequest,
  ProcessingResponse,
} from "./generated.js";

/** Read current visible assets without changing immutable catalog operation receipts. */
export function createAvailabilityApi(transport: KoinonTransport) {
  return {
    processing: (
      tenantId: string,
      input: ProcessingRequest,
      options: RequestOptions = {},
    ) =>
      transport.request<ProcessingResponse>(
        "POST",
        `/tenants/${encodeURIComponent(tenantId)}/knowledge-processing`,
        { ...options, body: input },
      ),
    observe: (
      tenantId: string,
      input: AvailabilityRequest,
      options: RequestOptions = {},
    ) =>
      transport.request<AvailabilityResponse>(
        "POST",
        `/tenants/${encodeURIComponent(tenantId)}/catalog/availability`,
        { ...options, body: input },
      ),
  };
}
