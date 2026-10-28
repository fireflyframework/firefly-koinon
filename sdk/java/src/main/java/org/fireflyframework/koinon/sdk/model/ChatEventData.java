// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ChatEventData contract. */
public record ChatEventData(
    @JsonProperty("proposal_update") ProposalUpdate proposalUpdate,
    @JsonProperty("tool_activity") ToolActivity toolActivity,
    @JsonProperty("answer_policy") AnswerPolicy answerPolicy,
    @JsonProperty("presentation") Presentation presentation,
    @JsonProperty("text") String text,
    @JsonProperty("stage") String stage,
    @JsonProperty("message") String message,
    @JsonProperty("status") MessageStatus status,
    @JsonProperty("code") String code,
    @JsonProperty("message_id") String messageId,
    @JsonProperty("artifact") OpenUIArtifact artifact,
    @JsonProperty("citation") Citation citation
) {

}
