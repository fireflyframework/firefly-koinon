// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ContentUpdate contract. */
public record ContentUpdate(
    @JsonProperty("asset") CatalogEntry asset,
    @JsonProperty("source") CatalogEntry source,
    @JsonProperty("table") CatalogEntry table,
    @JsonProperty("version") CatalogEntry version,
    @JsonProperty("effects") ContentEffects effects
) {

}
