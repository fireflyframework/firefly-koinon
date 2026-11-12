// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceRunPage contract. */
public record SourceRunPage(
    @JsonProperty("items") List<SourceRunOutput> items,
    @JsonProperty("next_cursor") String nextCursor
) {
    public SourceRunPage {
        items=items==null?null:List.copyOf(items);
    }

}
