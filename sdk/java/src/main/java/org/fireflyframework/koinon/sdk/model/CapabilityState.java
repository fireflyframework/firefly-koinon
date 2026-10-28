// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical CapabilityState contract. */
public record CapabilityState(
    @JsonProperty("supported") Boolean supported,
    @JsonProperty("verified") Boolean verified
) {

}
