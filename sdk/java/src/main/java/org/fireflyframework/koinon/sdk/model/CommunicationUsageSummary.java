// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical CommunicationUsageSummary contract. */
public record CommunicationUsageSummary(
    @JsonProperty("scope") CommunicationUsageSummaryScope scope,
    @JsonProperty("window_start") Instant windowStart,
    @JsonProperty("window_end") Instant windowEnd,
    @JsonProperty("time_zone") String timeZone,
    @JsonProperty("assistant_runs") Long assistantRuns,
    @JsonProperty("completed_runs") Long completedRuns,
    @JsonProperty("failed_runs") Long failedRuns,
    @JsonProperty("mcp_requests") Long mcpRequests,
    @JsonProperty("mcp_request_status") CommunicationUsageSummaryMcpRequestStatus mcpRequestStatus
) {

}
