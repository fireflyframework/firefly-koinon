// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;



/** Typed canonical Job contract. */
public record Job(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("resource_id") String resourceId,
    @JsonProperty("kind") String kind,
    @JsonProperty("status") String status,
    @JsonProperty("attempts") Long attempts,
    @JsonProperty("max_attempts") Long maxAttempts,
    @JsonProperty("progress") Long progress,
    @JsonProperty("error") String error,
    @JsonProperty("result") JsonNode result,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("updated_at") Instant updatedAt
) {
    public Job {
        result=ModelValues.json(result);
    }
    @Override public JsonNode result(){return ModelValues.json(result);}
}
