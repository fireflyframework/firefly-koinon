// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SystemLimit contract. */
public record SystemLimit(
    @JsonProperty("id") SystemLimitId id,
    @JsonProperty("value") Long value,
    @JsonProperty("unit") SystemLimitUnit unit,
    @JsonProperty("scope") SystemLimitScope scope
) {

}
