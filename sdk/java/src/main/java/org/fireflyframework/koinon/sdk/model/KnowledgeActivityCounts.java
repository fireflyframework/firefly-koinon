// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KnowledgeActivityCounts contract. */
public record KnowledgeActivityCounts(
    @JsonProperty("created") ObservedCount created,
    @JsonProperty("updated") ObservedCount updated,
    @JsonProperty("consulted") ObservedCount consulted
) {

}
