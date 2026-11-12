// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourcePreviewItem contract. */
public record SourcePreviewItem(
    @JsonProperty("item_id") String itemId,
    @JsonProperty("name") String name,
    @JsonProperty("kind") String kind,
    @JsonProperty("version") String version,
    @JsonProperty("filename") String filename,
    @JsonProperty("export_mime") String exportMime,
    @JsonProperty("reason") String reason,
    @JsonProperty("ancestry") List<String> ancestry,
    @JsonProperty("relative_path") List<String> relativePath,
    @JsonProperty("destination_relative_path") List<String> destinationRelativePath,
    @JsonProperty("collision") SourceMappingValidationItemCollision collision,
    @JsonProperty("size_bytes") Long sizeBytes,
    @JsonProperty("action") SourceMappingValidationItemAction action
) {
    public SourcePreviewItem {
        ancestry=ancestry==null?null:List.copyOf(ancestry);
        relativePath=relativePath==null?null:List.copyOf(relativePath);
        destinationRelativePath=destinationRelativePath==null?null:List.copyOf(destinationRelativePath);
    }

}
