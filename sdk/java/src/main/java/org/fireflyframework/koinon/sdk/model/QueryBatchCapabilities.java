// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical QueryBatchCapabilities contract. */
public record QueryBatchCapabilities(
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("processing_policy") QueryBatchCapabilitiesProcessingPolicy processingPolicy,
    @JsonProperty("automatic_unknown_replay") Boolean automaticUnknownReplay,
    @JsonProperty("shared_conversation") Boolean sharedConversation,
    @JsonProperty("connection_mode") QueryBatchCapabilitiesConnectionMode connectionMode,
    @JsonProperty("max_queries") Long maxQueries,
    @JsonProperty("max_question_characters") Long maxQuestionCharacters,
    @JsonProperty("max_question_bytes_per_batch") Long maxQuestionBytesPerBatch,
    @JsonProperty("max_result_bytes") Long maxResultBytes
) {

}
