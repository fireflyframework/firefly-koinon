// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical OrganizationPersonPage contract. */
public record OrganizationPersonPage(
    @JsonProperty("items") List<OrganizationPerson> items,
    @JsonProperty("total") Long total,
    @JsonProperty("page") Long page,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("pages") Long pages
) {
    public OrganizationPersonPage {
        items=items==null?null:List.copyOf(items);
    }

}
