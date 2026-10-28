// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical IdentityProviderPage contract. */
public record IdentityProviderPage(
    @JsonProperty("items") List<IdentityProvider> items,
    @JsonProperty("total") Long total,
    @JsonProperty("page") Long page,
    @JsonProperty("page_size") Long pageSize,
    @JsonProperty("pages") Long pages
) {
    public IdentityProviderPage {
        items=items==null?null:List.copyOf(items);
    }

}
