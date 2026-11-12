// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;



/** Typed canonical ExportBrowsePage contract. */
public record ExportBrowsePage(
    @JsonProperty("items") List<Export> items,
    @JsonProperty("next_cursor") String nextCursor,
    @JsonProperty("total") JsonNode total,
    @JsonProperty("total_is_exact") Boolean totalIsExact
) {
    public ExportBrowsePage {
        items=items==null?null:List.copyOf(items);
        total=ModelValues.json(total);
    }
    @Override public JsonNode total(){return ModelValues.json(total);}
}
