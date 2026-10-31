// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.Map;



/** Typed canonical QueryBatchView contract. */
public record QueryBatchView(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("status") QueryBatchViewStatus status,
    @JsonProperty("revision") Integer revision,
    @JsonProperty("total_items") Integer totalItems,
    @JsonProperty("counts") Map<String,Long> counts,
    @JsonProperty("cancellation_requested") Boolean cancellationRequested,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("expires_at") Instant expiresAt
) {
    public QueryBatchView {
        counts=counts==null?null:Map.copyOf(counts);
    }

}
