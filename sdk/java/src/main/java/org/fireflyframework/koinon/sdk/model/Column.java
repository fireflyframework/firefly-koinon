// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical Column contract. */
public record Column(
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("data_type") String dataType,
    @JsonProperty("description") String description,
    @JsonProperty("pii_tag") String piiTag
) {

}
