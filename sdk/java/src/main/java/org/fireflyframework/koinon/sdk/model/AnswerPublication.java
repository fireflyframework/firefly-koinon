// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AnswerPublication contract. */
public record AnswerPublication(
    @JsonProperty("format") AnswerPublicationFormat format,
    @JsonProperty("chunk_size") Long chunkSize,
    @JsonProperty("chunk_count") Long chunkCount,
    @JsonProperty("text_sha256") String textSha256
) {

}
