// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;



/** Typed canonical TableSnapshotReadPage contract. */
public record TableSnapshotReadPage(
    @JsonProperty("items") List<TableSnapshotSummary> items,
    @JsonProperty("next_cursor") String nextCursor,
    @JsonProperty("total") JsonNode total,
    @JsonProperty("pages") JsonNode pages,
    @JsonProperty("total_is_exact") Boolean totalIsExact,
    @JsonProperty("current_snapshot_id") String currentSnapshotId
) {
    public TableSnapshotReadPage {
        items=items==null?null:List.copyOf(items);
        total=ModelValues.json(total);
        pages=ModelValues.json(pages);
    }
    @Override public JsonNode total(){return ModelValues.json(total);}
    @Override public JsonNode pages(){return ModelValues.json(pages);}
}
