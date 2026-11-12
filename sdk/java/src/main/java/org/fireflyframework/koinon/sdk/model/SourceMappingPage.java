// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceMappingPage contract. */
public record SourceMappingPage(
    @JsonProperty("items") List<SourceMappingSummary> items,
    @JsonProperty("next_cursor") String nextCursor
) {
    public SourceMappingPage {
        items=items==null?null:List.copyOf(items);
    }

}
