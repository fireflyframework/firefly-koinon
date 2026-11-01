// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical HealthCounts contract. */
public record HealthCounts(
    @JsonProperty("observed_total") Integer observedTotal,
    @JsonProperty("observed_ready") Integer observedReady,
    @JsonProperty("observed_pending") Integer observedPending,
    @JsonProperty("observed_running") Integer observedRunning,
    @JsonProperty("observed_failed") Integer observedFailed
) {

}
