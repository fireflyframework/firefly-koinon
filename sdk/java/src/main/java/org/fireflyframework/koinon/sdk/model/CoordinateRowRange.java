// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical CoordinateRowRange contract. */
public record CoordinateRowRange(
    @JsonProperty("output_start") Long outputStart,
    @JsonProperty("count") Long count,
    @JsonProperty("source_start") Long sourceStart,
    @JsonProperty("source_stride") Long sourceStride
) {

}
