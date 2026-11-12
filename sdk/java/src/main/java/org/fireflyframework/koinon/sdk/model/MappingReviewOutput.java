// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical MappingReviewOutput contract. */
public record MappingReviewOutput(
    @JsonProperty("id") String id,
    @JsonProperty("revision") Long revision,
    @JsonProperty("status") MappingReviewOutputStatus status,
    @JsonProperty("expires_at") Instant expiresAt
) {

}
