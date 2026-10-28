// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical PrivateChunkView contract. */
public record PrivateChunkView(
    @JsonProperty("id") String id,
    @JsonProperty("attachment_id") String attachmentId,
    @JsonProperty("index") Long index,
    @JsonProperty("text") String text,
    @JsonProperty("page") Long page,
    @JsonProperty("section_path") List<String> sectionPath,
    @JsonProperty("char_start") Long charStart,
    @JsonProperty("char_end") Long charEnd,
    @JsonProperty("offset_basis") PrivateChunkViewOffsetBasis offsetBasis,
    @JsonProperty("sha256") String sha256
) {
    public PrivateChunkView {
        sectionPath=sectionPath==null?null:List.copyOf(sectionPath);
    }

}
