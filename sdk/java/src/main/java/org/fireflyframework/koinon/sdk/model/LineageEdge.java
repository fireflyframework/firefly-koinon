// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical LineageEdge contract. */
public record LineageEdge(
    @JsonProperty("source") String source,
    @JsonProperty("target") String target,
    @JsonProperty("label") String label
) {

}
