// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical CatalogSummary contract. */
public record CatalogSummary(
    @JsonProperty("child_count") Long childCount,
    @JsonProperty("document_count") Long documentCount,
    @JsonProperty("dataset_count") Long datasetCount,
    @JsonProperty("table_count") Long tableCount,
    @JsonProperty("row_count") Long rowCount,
    @JsonProperty("column_count") Long columnCount,
    @JsonProperty("page_count") Long pageCount,
    @JsonProperty("size_bytes") Long sizeBytes,
    @JsonProperty("format") String format,
    @JsonProperty("language") String language,
    @JsonProperty("tags") List<String> tags
) {
    public CatalogSummary {
        tags=tags==null?null:List.copyOf(tags);
    }

}
