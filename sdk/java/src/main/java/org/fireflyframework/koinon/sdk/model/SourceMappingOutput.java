// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical SourceMappingOutput contract. */
public record SourceMappingOutput(
    @JsonProperty("id") String id,
    @JsonProperty("revision") Long revision,
    @JsonProperty("policy_revision") Long policyRevision,
    @JsonProperty("latest_review_revision") Long latestReviewRevision,
    @JsonProperty("control_revision") Long controlRevision,
    @JsonProperty("connection_id") String connectionId,
    @JsonProperty("policy") MappingReviewInput policy,
    @JsonProperty("presentation") SourceMappingPresentation presentation,
    @JsonProperty("status") SourceMappingOutputStatus status,
    @JsonProperty("next_run_at") Instant nextRunAt,
    @JsonProperty("can_pause") Boolean canPause,
    @JsonProperty("can_resume") Boolean canResume,
    @JsonProperty("can_retire") Boolean canRetire,
    @JsonProperty("can_sync") Boolean canSync
) {

}
