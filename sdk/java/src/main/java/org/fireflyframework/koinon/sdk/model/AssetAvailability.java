// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AssetAvailability contract. */
public record AssetAvailability(
    @JsonProperty("phase") AssetAvailabilityPhase phase,
    @JsonProperty("read") AvailabilityCapability read,
    @JsonProperty("search") AvailabilityCapability search,
    @JsonProperty("query") AvailabilityCapability query,
    @JsonProperty("revision") AvailabilityRevision revision,
    @JsonProperty("latest_attempt") AvailabilityAttempt latestAttempt
) {

}
