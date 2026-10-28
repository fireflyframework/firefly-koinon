// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DocumentChunk contract. */
public record DocumentChunk(
    @JsonProperty("id") String id,
    @JsonProperty("index") Long index,
    @JsonProperty("total_chunks") Long totalChunks,
    @JsonProperty("text") String text,
    @JsonProperty("char_start") Long charStart,
    @JsonProperty("char_end") Long charEnd,
    @JsonProperty("page") Long page,
    @JsonProperty("section_path") String sectionPath,
    @JsonProperty("embedding_model") String embeddingModel
) {

}
