// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical MetricsObservation contract. */
public record MetricsObservation(
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("available") Boolean available,
    @JsonProperty("status") ObservationStatus status,
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("reason") String reason,
    @JsonProperty("exporter_configured") Boolean exporterConfigured,
    @JsonProperty("names") List<String> names
) {
    public MetricsObservation {
        names=names==null?null:List.copyOf(names);
    }

}
