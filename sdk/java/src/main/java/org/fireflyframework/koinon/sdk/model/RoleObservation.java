// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical RoleObservation contract. */
public record RoleObservation(
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("available") Boolean available,
    @JsonProperty("status") ObservationStatus status,
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("reason") String reason,
    @JsonProperty("superuser") Boolean superuser,
    @JsonProperty("bypass_rls") Boolean bypassRls
) {

}
