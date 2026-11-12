// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceMappingValidationItemPage contract. */
public record SourceMappingValidationItemPage(
    @JsonProperty("validation_id") String validationId,
    @JsonProperty("revision") Long revision,
    @JsonProperty("items") List<SourceMappingValidationItem> items,
    @JsonProperty("visible_count") Long visibleCount,
    @JsonProperty("next_cursor") String nextCursor,
    @JsonProperty("total") Long total
) {
    public SourceMappingValidationItemPage {
        items=items==null?null:List.copyOf(items);
    }

}
