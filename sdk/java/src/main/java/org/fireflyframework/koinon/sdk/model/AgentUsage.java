// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;



/** Typed canonical AgentUsage contract. */
public record AgentUsage(
    @JsonProperty("agent") String agent,
    @JsonProperty("model") String model,
    @JsonProperty("input_tokens") Long inputTokens,
    @JsonProperty("output_tokens") Long outputTokens,
    @JsonProperty("total_tokens") Long totalTokens,
    @JsonProperty("cost_usd") BigDecimal costUsd,
    @JsonProperty("latency_ms") BigDecimal latencyMs,
    @JsonProperty("calls") Long calls
) {

}
