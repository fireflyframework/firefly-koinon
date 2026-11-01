// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical ActivityCoverage contract. */
public record ActivityCoverage(
    @JsonProperty("observed_since") Instant observedSince,
    @JsonProperty("complete_window") Boolean completeWindow,
    @JsonProperty("missing_observations") Long missingObservations,
    @JsonProperty("reasons") List<String> reasons
) {
    public ActivityCoverage {
        reasons=reasons==null?null:List.copyOf(reasons);
    }

}
