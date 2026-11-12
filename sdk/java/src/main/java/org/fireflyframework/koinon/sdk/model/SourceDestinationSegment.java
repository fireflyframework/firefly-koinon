// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceDestinationSegment contract. */
public record SourceDestinationSegment(
    @JsonProperty("id") String id,
    @JsonProperty("kind") String kind,
    @JsonProperty("name") String name
) {

}
