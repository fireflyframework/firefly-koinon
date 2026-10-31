// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical BrandingPalette contract. */
public record BrandingPalette(
    @JsonProperty("surface") String surface,
    @JsonProperty("canvas") String canvas,
    @JsonProperty("text") String text,
    @JsonProperty("muted") String muted,
    @JsonProperty("line") String line,
    @JsonProperty("action") String action,
    @JsonProperty("action_text") String actionText,
    @JsonProperty("accent") String accent
) {

}
