// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical AttachmentEvidenceItem contract. */
public record AttachmentEvidenceItem(
    @JsonProperty("id") String id,
    @JsonProperty("filename") String filename,
    @JsonProperty("media_type") String mediaType,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("revision") Long revision,
    @JsonProperty("complete") Boolean complete,
    @JsonProperty("chunk_ids") List<String> chunkIds,
    @JsonProperty("total_chunks") Long totalChunks,
    @JsonProperty("warnings") List<String> warnings
) {
    public AttachmentEvidenceItem {
        chunkIds=chunkIds==null?null:List.copyOf(chunkIds);
        warnings=warnings==null?null:List.copyOf(warnings);
    }

}
