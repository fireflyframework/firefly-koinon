// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ChatEventData contract. */
public record ChatEventData(
    @JsonProperty("chunk_index") Long chunkIndex,
    @JsonProperty("chunk_count") Long chunkCount,
    @JsonProperty("text_offset") Long textOffset,
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
    public ChatEventData(ProposalUpdate proposalUpdate, ToolActivity toolActivity, AnswerPolicy answerPolicy, Presentation presentation, String text, String stage, String message, MessageStatus status, String code, String messageId, OpenUIArtifact artifact, Citation citation){this(null,null,null,proposalUpdate,toolActivity,answerPolicy,presentation,text,stage,message,status,code,messageId,artifact,citation);}

}
