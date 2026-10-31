// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical MemoryTurnReference contract. */
public record MemoryTurnReference(
    @JsonProperty("run_id") String runId,
    @JsonProperty("generation_id") String generationId,
    @JsonProperty("thread_id") String threadId,
    @JsonProperty("conversation_title") String conversationTitle,
    @JsonProperty("user_created_at") Instant userCreatedAt,
    @JsonProperty("user_message_id") String userMessageId,
    @JsonProperty("user_sha256") String userSha256,
    @JsonProperty("answer_message_id") String answerMessageId,
    @JsonProperty("answer_sha256") String answerSha256,
    @JsonProperty("answer_included") Boolean answerIncluded,
    @JsonProperty("availability") MemoryTurnReferenceAvailability availability
) {

}
