// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical FeatureCapability contract. */
public record FeatureCapability(
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("available") Boolean available,
    @JsonProperty("reason") String reason
) {

}
