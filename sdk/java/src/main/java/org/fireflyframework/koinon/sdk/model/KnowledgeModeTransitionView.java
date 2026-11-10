// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.Map;



/** Typed canonical KnowledgeModeTransitionView contract. */
public record KnowledgeModeTransitionView(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("job_id") String jobId,
    @JsonProperty("revision") Long revision,
    @JsonProperty("base_revision") Long baseRevision,
    @JsonProperty("base_digest") String baseDigest,
    @JsonProperty("active_mode") KnowledgeAnswerMode activeMode,
    @JsonProperty("requested_mode") KnowledgeAnswerMode requestedMode,
    @JsonProperty("requested_settings") OrganizationKnowledgeSettingsInput requestedSettings,
    @JsonProperty("status") KnowledgeModeTransitionViewStatus status,
    @JsonProperty("stage") KnowledgeModeTransitionViewStage stage,
    @JsonProperty("counters") Map<String,Long> counters,
    @JsonProperty("stage_milliseconds") Map<String,Long> stageMilliseconds,
    @JsonProperty("pending_index_recoveries") Long pendingIndexRecoveries,
    @JsonProperty("progress_reason") KnowledgeModeTransitionViewProgressReason progressReason,
    @JsonProperty("error_code") String errorCode,
    @JsonProperty("error") String error,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("updated_at") Instant updatedAt
) {
    public KnowledgeModeTransitionView {
        counters=counters==null?null:Map.copyOf(counters);
        stageMilliseconds=stageMilliseconds==null?null:Map.copyOf(stageMilliseconds);
    }

}
