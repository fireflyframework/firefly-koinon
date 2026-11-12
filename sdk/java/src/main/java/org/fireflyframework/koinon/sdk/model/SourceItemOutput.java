// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceItemOutput contract. */
public record SourceItemOutput(
    @JsonProperty("item_id") String itemId,
    @JsonProperty("name") String name,
    @JsonProperty("kind") SourceItemOutputKind kind,
    @JsonProperty("version") String version,
    @JsonProperty("size_bytes") Long sizeBytes,
    @JsonProperty("mime_type") String mimeType,
    @JsonProperty("parents") List<String> parents,
    @JsonProperty("can_download") Boolean canDownload,
    @JsonProperty("modified_at") String modifiedAt
) {
    public SourceItemOutput {
        parents=parents==null?null:List.copyOf(parents);
    }

}
