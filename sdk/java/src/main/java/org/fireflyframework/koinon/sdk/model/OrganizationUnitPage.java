// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical OrganizationUnitPage contract. */
public record OrganizationUnitPage(
    @JsonProperty("items") List<OrganizationUnit> items,
    @JsonProperty("total") Long total,
    @JsonProperty("page") Long page,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("pages") Long pages
) {
    public OrganizationUnitPage {
        items=items==null?null:List.copyOf(items);
    }

}
