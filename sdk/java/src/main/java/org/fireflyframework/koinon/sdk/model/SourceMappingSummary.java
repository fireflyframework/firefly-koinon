// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical SourceMappingSummary contract. */
public record SourceMappingSummary(
    @JsonProperty("id") String id,
    @JsonProperty("status") SourceMappingOutputStatus status,
    @JsonProperty("connection_id") String connectionId,
    @JsonProperty("policy_revision") Long policyRevision,
    @JsonProperty("latest_review_revision") Long latestReviewRevision,
    @JsonProperty("control_revision") Long controlRevision,
    @JsonProperty("next_run_at") Instant nextRunAt,
    @JsonProperty("presentation") SourceMappingPresentation presentation
) {

}
