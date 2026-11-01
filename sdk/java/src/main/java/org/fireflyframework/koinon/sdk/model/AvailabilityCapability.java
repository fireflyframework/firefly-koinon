// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AvailabilityCapability contract. */
public record AvailabilityCapability(
    @JsonProperty("state") AvailabilityCapabilityState state,
    @JsonProperty("reason") String reason
) {

}
