// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceMappingValidationItem contract. */
public record SourceMappingValidationItem(
    @JsonProperty("item_id") String itemId,
    @JsonProperty("name") String name,
    @JsonProperty("kind") SourceItemOutputKind kind,
    @JsonProperty("version") String version,
    @JsonProperty("filename") String filename,
    @JsonProperty("export_mime") String exportMime,
    @JsonProperty("reason") String reason,
    @JsonProperty("relative_path") List<String> relativePath,
    @JsonProperty("destination_relative_path") List<String> destinationRelativePath,
    @JsonProperty("size_bytes") Long sizeBytes,
    @JsonProperty("collision") SourceMappingValidationItemCollision collision,
    @JsonProperty("action") SourceMappingValidationItemAction action
) {
    public SourceMappingValidationItem {
        relativePath=relativePath==null?null:List.copyOf(relativePath);
        destinationRelativePath=destinationRelativePath==null?null:List.copyOf(destinationRelativePath);
    }

}
