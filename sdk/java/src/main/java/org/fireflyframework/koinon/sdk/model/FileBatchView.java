// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.Map;



/** Typed canonical FileBatchView contract. */
public record FileBatchView(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("destination") BulkDestination destination,
    @JsonProperty("status") FileBatchViewStatus status,
    @JsonProperty("revision") Integer revision,
    @JsonProperty("total_items") Long totalItems,
    @JsonProperty("total_bytes") Long totalBytes,
    @JsonProperty("counts") Map<String,Long> counts,
    @JsonProperty("cancellation_requested") Boolean cancellationRequested,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("expires_at") Instant expiresAt
) {
    public FileBatchView {
        counts=counts==null?null:Map.copyOf(counts);
    }

}
