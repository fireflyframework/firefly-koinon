// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical CorporateProfileFieldObservation contract. */
public record CorporateProfileFieldObservation(
    @JsonProperty("field") ProfileFieldName field,
    @JsonProperty("source") ProfileObservationSource source,
    @JsonProperty("status") ProfileFieldStatus status,
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("code") String code
) {

}
