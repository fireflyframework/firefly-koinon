// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical DocumentChunks contract. */
public record DocumentChunks(
    @JsonProperty("document_id") String documentId,
    @JsonProperty("source_id") String sourceId,
    @JsonProperty("native_source_id") String nativeSourceId,
    @JsonProperty("source_version_id") String sourceVersionId,
    @JsonProperty("extraction_id") String extractionId,
    @JsonProperty("items") List<DocumentChunk> items,
    @JsonProperty("offset") Long offset,
    @JsonProperty("limit") Long limit,
    @JsonProperty("total") Long total,
    @JsonProperty("next_offset") Long nextOffset
) {
    public DocumentChunks {
        items=items==null?null:List.copyOf(items);
    }

}
