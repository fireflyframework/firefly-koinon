// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.Map;



/** Typed canonical CatalogBrowseOutput contract. */
public record CatalogBrowseOutput(
    @JsonProperty("items") List<CatalogEntry> items,
    @JsonProperty("actors") Map<String,AuthorSummary> actors,
    @JsonProperty("next_cursor") String nextCursor,
    @JsonProperty("summaries") Map<String,CatalogSummary> summaries,
    @JsonProperty("total") JsonNode total,
    @JsonProperty("total_is_exact") Boolean totalIsExact
) {
    public CatalogBrowseOutput {
        items=items==null?null:List.copyOf(items);
        actors=actors==null?null:Map.copyOf(actors);
        summaries=summaries==null?null:Map.copyOf(summaries);
        total=ModelValues.json(total);
    }
    @Override public JsonNode total(){return ModelValues.json(total);}
}
