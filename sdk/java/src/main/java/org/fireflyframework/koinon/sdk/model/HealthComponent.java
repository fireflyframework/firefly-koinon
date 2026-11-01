// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical HealthComponent contract. */
public record HealthComponent(
    @JsonProperty("id") HealthComponentId id,
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("status") HealthComponentStatus status,
    @JsonProperty("basis") HealthComponentBasis basis,
    @JsonProperty("freshness") HealthComponentFreshness freshness,
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("reason") HealthComponentReason reason,
    @JsonProperty("remediation") HealthComponentRemediation remediation,
    @JsonProperty("counts") HealthCounts counts,
    @JsonProperty("coverage") HealthComponentCoverage coverage
) {

}
