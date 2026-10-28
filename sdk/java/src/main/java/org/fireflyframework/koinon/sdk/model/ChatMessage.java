// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical ChatMessage contract. */
public record ChatMessage(
    @JsonProperty("tool_activities") List<ToolActivity> toolActivities,
    @JsonProperty("tool_activity_count") Long toolActivityCount,
    @JsonProperty("tool_activity_has_more") Boolean toolActivityHasMore,
    @JsonProperty("attachments") List<AttachmentHistorySummary> attachments,
    @JsonProperty("answer_policy") AnswerPolicy answerPolicy,
    @JsonProperty("presentation") Presentation presentation,
    @JsonProperty("event_cursor") String eventCursor,
    @JsonProperty("id") String id,
    @JsonProperty("run_id") String runId,
    @JsonProperty("role") ChatMessageRole role,
    @JsonProperty("text") String text,
    @JsonProperty("status") MessageStatus status,
    @JsonProperty("citations") List<Citation> citations,
    @JsonProperty("artifacts") List<OpenUIArtifact> artifacts,
    @JsonProperty("created_at") Instant createdAt
) {
    public ChatMessage {
        toolActivities=toolActivities==null?null:List.copyOf(toolActivities);
        attachments=attachments==null?null:List.copyOf(attachments);
        citations=citations==null?null:List.copyOf(citations);
        artifacts=artifacts==null?null:List.copyOf(artifacts);
    }

}
