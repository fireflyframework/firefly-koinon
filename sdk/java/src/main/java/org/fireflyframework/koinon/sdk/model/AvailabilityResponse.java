// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.Map;



/** Typed canonical AvailabilityResponse contract. */
public record AvailabilityResponse(
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("items") Map<String,AssetAvailability> items
) {
    public AvailabilityResponse {
        items=items==null?null:Map.copyOf(items);
    }

}
