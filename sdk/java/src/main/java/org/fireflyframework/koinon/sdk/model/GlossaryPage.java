// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical GlossaryPage contract. */
public record GlossaryPage(
    @JsonProperty("items") List<GlossaryTermRead> items,
    @JsonProperty("total") Long total,
    @JsonProperty("limit") Long limit,
    @JsonProperty("offset") Long offset,
    @JsonProperty("has_more") Boolean hasMore
) {
    public GlossaryPage {
        items=items==null?null:List.copyOf(items);
    }

}
