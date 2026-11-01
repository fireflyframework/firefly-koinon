// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical HealthSummary contract. */
public record HealthSummary(
    @JsonProperty("passed") Integer passed,
    @JsonProperty("failed") Integer failed,
    @JsonProperty("unknown") Integer unknown,
    @JsonProperty("disabled") Integer disabled
) {

}
