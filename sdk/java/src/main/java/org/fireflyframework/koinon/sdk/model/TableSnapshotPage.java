// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical TableSnapshotPage contract. */
public record TableSnapshotPage(
    @JsonProperty("items") List<TableSnapshotSummary> items,
    @JsonProperty("total") Long total,
    @JsonProperty("page") Long page,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("pages") Long pages,
    @JsonProperty("has_next") Boolean hasNext,
    @JsonProperty("has_previous") Boolean hasPrevious,
    @JsonProperty("current_snapshot_id") String currentSnapshotId
) {
    public TableSnapshotPage {
        items=items==null?null:List.copyOf(items);
    }

}
