// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical ExternalReviewView contract. */
public record ExternalReviewView(
    @JsonProperty("id") String id,
    @JsonProperty("review") KnowledgeIntent review,
    @JsonProperty("status") ExternalReviewViewStatus status,
    @JsonProperty("expires_at") Instant expiresAt
) {

}
