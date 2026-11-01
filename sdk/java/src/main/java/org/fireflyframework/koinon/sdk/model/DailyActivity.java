// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DailyActivity contract. */
public record DailyActivity(
    @JsonProperty("local_date") String localDate,
    @JsonProperty("knowledge") KnowledgeActivityCounts knowledge,
    @JsonProperty("mcp_tool_calls") ObservedCount mcpToolCalls
) {

}
