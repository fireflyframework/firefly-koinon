// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical BrandingValues contract. */
public record BrandingValues(
    @JsonProperty("product_name") String productName,
    @JsonProperty("assistant_name") String assistantName,
    @JsonProperty("logo_light") String logoLight,
    @JsonProperty("logo_dark") String logoDark,
    @JsonProperty("symbol") String symbol,
    @JsonProperty("favicon") String favicon,
    @JsonProperty("palette") BrandingPalettes palette,
    @JsonProperty("font_family") BrandingValuesFontFamily fontFamily
) {

}
