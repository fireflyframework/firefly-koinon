// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DocumentHistoryPagination contract. */
public record DocumentHistoryPagination(
    @JsonProperty("total") Long total,
    @JsonProperty("page") Long page,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("pages") Long pages,
    @JsonProperty("has_next") Boolean hasNext,
    @JsonProperty("has_previous") Boolean hasPrevious
) {

}
