// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AvailabilityAttempt contract. */
public record AvailabilityAttempt(
    @JsonProperty("id") String id,
    @JsonProperty("operation") String operation,
    @JsonProperty("state") AssetAvailabilityPhase state
) {

}
