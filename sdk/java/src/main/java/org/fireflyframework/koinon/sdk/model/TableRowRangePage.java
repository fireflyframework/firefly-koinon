// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical TableRowRangePage contract. */
public record TableRowRangePage(
    @JsonProperty("manifest") TableCoordinateManifest manifest,
    @JsonProperty("total") Long total,
    @JsonProperty("page") Long page,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("pages") Long pages,
    @JsonProperty("has_next") Boolean hasNext,
    @JsonProperty("has_previous") Boolean hasPrevious,
    @JsonProperty("items") List<CoordinateRowRange> items
) {
    public TableRowRangePage {
        items=items==null?null:List.copyOf(items);
    }

}
