// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical ProcessingActivity contract. */
public record ProcessingActivity(
    @JsonProperty("id") String id,
    @JsonProperty("resource_id") String resourceId,
    @JsonProperty("operation") String operation,
    @JsonProperty("state") AssetAvailabilityPhase state,
    @JsonProperty("updated_at") Instant updatedAt,
    @JsonProperty("availability") AssetAvailability availability
) {

}
