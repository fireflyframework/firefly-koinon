// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical IdentityValidation contract. */
public record IdentityValidation(
    @JsonProperty("id") String id,
    @JsonProperty("candidate_revision") Long candidateRevision,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("checks") List<IdentityCheck> checks,
    @JsonProperty("status") IdentityValidationStatus status,
    @JsonProperty("authorization_url") String authorizationUrl
) {
    public IdentityValidation {
        checks=checks==null?null:List.copyOf(checks);
    }

}
