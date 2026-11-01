// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical McpActivityCounts contract. */
public record McpActivityCounts(
    @JsonProperty("requests") ObservedCount requests,
    @JsonProperty("tool_calls") ObservedCount toolCalls,
    @JsonProperty("succeeded") ObservedCount succeeded,
    @JsonProperty("failed") ObservedCount failed,
    @JsonProperty("rejected") ObservedCount rejected,
    @JsonProperty("average_duration_ms") ObservedCount averageDurationMs,
    @JsonProperty("p95_duration_ms") ObservedCount p95DurationMs,
    @JsonProperty("tool_cancelled") ObservedCount toolCancelled,
    @JsonProperty("request_succeeded") ObservedCount requestSucceeded,
    @JsonProperty("request_failed") ObservedCount requestFailed,
    @JsonProperty("request_rejected") ObservedCount requestRejected,
    @JsonProperty("request_cancelled") ObservedCount requestCancelled
) {

}
