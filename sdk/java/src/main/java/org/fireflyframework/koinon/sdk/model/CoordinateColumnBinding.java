// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;



/** Typed canonical CoordinateColumnBinding contract. */
public record CoordinateColumnBinding(
    @JsonProperty("output_position") Long outputPosition,
    @JsonProperty("source_field_index") Long sourceFieldIndex,
    @JsonProperty("source_path") List<JsonNode> sourcePath,
    @JsonProperty("source_type") String sourceType,
    @JsonProperty("header_cells") List<CoordinateHeaderCell> headerCells
) {
    public CoordinateColumnBinding {
        sourcePath=ModelValues.jsonList(sourcePath);
        headerCells=headerCells==null?null:List.copyOf(headerCells);
    }
    @Override public List<JsonNode> sourcePath(){return ModelValues.jsonList(sourcePath);}
}
