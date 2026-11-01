// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ModelActivityCounts contract. */
public record ModelActivityCounts(
    @JsonProperty("input_tokens") ObservedCount inputTokens,
    @JsonProperty("output_tokens") ObservedCount outputTokens,
    @JsonProperty("embedding_tokens") ObservedCount embeddingTokens,
    @JsonProperty("cost") ObservedCost cost,
    @JsonProperty("external_client_consumption") McpReviewSupportClientSupport externalClientConsumption
) {

}
