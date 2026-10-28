// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical Citation contract. */
public record Citation(
    @JsonProperty("document_id") String documentId,
    @JsonProperty("chunk_id") String chunkId,
    @JsonProperty("section") String section,
    @JsonProperty("url") String url,
    @JsonProperty("id") String id,
    @JsonProperty("source_id") String sourceId,
    @JsonProperty("asset_id") String assetId,
    @JsonProperty("title") String title,
    @JsonProperty("text") String text,
    @JsonProperty("page") Long page
) {

}
