// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical IdentityCheck contract. */
public record IdentityCheck(
    @JsonProperty("id") String id,
    @JsonProperty("status") IdentityCheckStatus status,
    @JsonProperty("message") String message,
    @JsonProperty("supported") Boolean supported,
    @JsonProperty("verified") Boolean verified,
    @JsonProperty("available") Boolean available,
    @JsonProperty("observed_at") Instant observedAt
) {

}
