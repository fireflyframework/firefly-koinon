// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical SourceMappingValidationOutput contract. */
public record SourceMappingValidationOutput(
    @JsonProperty("validation_id") String validationId,
    @JsonProperty("revision") Long revision,
    @JsonProperty("state") SourceMappingValidationOutputState state,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("continuation_token") String continuationToken,
    @JsonProperty("enumeration_complete") Boolean enumerationComplete,
    @JsonProperty("observed_count") Long observedCount,
    @JsonProperty("total") Long total,
    @JsonProperty("manifest_sha256") String manifestSha256,
    @JsonProperty("reason_code") SourceMappingValidationOutputReasonCode reasonCode
) {

}
