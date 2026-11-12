// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceRunItemPage contract. */
public record SourceRunItemPage(
    @JsonProperty("items") List<SourceRunItem> items,
    @JsonProperty("next_cursor") String nextCursor
) {
    public SourceRunItemPage {
        items=items==null?null:List.copyOf(items);
    }

}
