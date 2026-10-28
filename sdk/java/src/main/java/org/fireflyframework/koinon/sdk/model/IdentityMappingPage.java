// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical IdentityMappingPage contract. */
public record IdentityMappingPage(
    @JsonProperty("items") List<IdentityMapping> items,
    @JsonProperty("total") Long total,
    @JsonProperty("page") Long page,
    @JsonProperty("page_size") Long pageSize,
    @JsonProperty("pages") Long pages
) {
    public IdentityMappingPage {
        items=items==null?null:List.copyOf(items);
    }

}
