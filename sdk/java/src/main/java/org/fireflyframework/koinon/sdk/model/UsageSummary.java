// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;
import java.util.List;



/** Typed canonical UsageSummary contract. */
public record UsageSummary(
    @JsonProperty("total_input_tokens") Long totalInputTokens,
    @JsonProperty("total_output_tokens") Long totalOutputTokens,
    @JsonProperty("total_tokens") Long totalTokens,
    @JsonProperty("total_cost_usd") BigDecimal totalCostUsd,
    @JsonProperty("total_latency_ms") BigDecimal totalLatencyMs,
    @JsonProperty("by_agent") List<AgentUsage> byAgent
) {
    public UsageSummary {
        byAgent=byAgent==null?null:List.copyOf(byAgent);
    }

}
