// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ToolActivity contract. */
public record ToolActivity(
    @JsonProperty("call_id") String callId,
    @JsonProperty("tool_name") ToolActivityToolName toolName,
    @JsonProperty("status") MessageStatus status,
    @JsonProperty("occurred_at") String occurredAt,
    @JsonProperty("started_at") String startedAt,
    @JsonProperty("finished_at") String finishedAt,
    @JsonProperty("duration_ms") Long durationMs,
    @JsonProperty("summary") String summary,
    @JsonProperty("result_id") String resultId
) {

}
