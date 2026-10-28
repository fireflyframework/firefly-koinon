// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical LineageNode contract. */
public record LineageNode(
    @JsonProperty("id") String id,
    @JsonProperty("label") String label,
    @JsonProperty("kind") String kind
) {

}
