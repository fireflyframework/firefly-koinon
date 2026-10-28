// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical CatalogProposalBefore contract. */
public record CatalogProposalBefore(
    @JsonProperty("name") String name,
    @JsonProperty("description") String description
) {

}
