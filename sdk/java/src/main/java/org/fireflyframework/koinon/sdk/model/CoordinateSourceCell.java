// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;



/** Typed canonical CoordinateSourceCell contract. */
public record CoordinateSourceCell(
    @JsonProperty("output_row") Long outputRow,
    @JsonProperty("output_column") Long outputColumn,
    @JsonProperty("source_row") Long sourceRow,
    @JsonProperty("source_column") Long sourceColumn,
    @JsonProperty("source_path") List<JsonNode> sourcePath,
    @JsonProperty("header_cells") List<CoordinateHeaderCell> headerCells,
    @JsonProperty("source_type") String sourceType
) {
    public CoordinateSourceCell {
        sourcePath=ModelValues.jsonList(sourcePath);
        headerCells=headerCells==null?null:List.copyOf(headerCells);
    }
    @Override public List<JsonNode> sourcePath(){return ModelValues.jsonList(sourcePath);}
}
