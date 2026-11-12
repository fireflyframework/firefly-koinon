// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;



/** Typed canonical MessageBrowsePage contract. */
public record MessageBrowsePage(
    @JsonProperty("items") List<JsonNode> items,
    @JsonProperty("next_cursor") String nextCursor,
    @JsonProperty("total") JsonNode total,
    @JsonProperty("total_is_exact") Boolean totalIsExact
) {
    public MessageBrowsePage {
        items=ModelValues.jsonList(items);
        total=ModelValues.json(total);
    }
    @Override public List<JsonNode> items(){return ModelValues.jsonList(items);}
    @Override public JsonNode total(){return ModelValues.json(total);}
}
