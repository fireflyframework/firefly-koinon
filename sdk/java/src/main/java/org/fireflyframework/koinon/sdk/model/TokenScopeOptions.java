// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical TokenScopeOptions contract. */
public record TokenScopeOptions(
    @JsonProperty("items") List<TokenScope> items,
    @JsonProperty("max_lifetime_days") Long maxLifetimeDays,
    @JsonProperty("max_active_per_user") Long maxActivePerUser
) {
    public TokenScopeOptions {
        items=items==null?null:List.copyOf(items);
    }

}
