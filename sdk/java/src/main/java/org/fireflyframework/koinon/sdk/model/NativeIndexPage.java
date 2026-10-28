// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical NativeIndexPage contract. */
public record NativeIndexPage(
    @JsonProperty("items") List<NativeIndexChoice> items,
    @JsonProperty("total") Long total,
    @JsonProperty("limit") Long limit,
    @JsonProperty("offset") Long offset
) {
    public NativeIndexPage {
        items=items==null?null:List.copyOf(items);
    }

}
