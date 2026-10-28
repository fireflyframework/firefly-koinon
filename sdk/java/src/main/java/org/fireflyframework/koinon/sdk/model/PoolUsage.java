// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical PoolUsage contract. */
public record PoolUsage(
    @JsonProperty("size") Long size,
    @JsonProperty("checked_out") Long checkedOut,
    @JsonProperty("overflow") Long overflow
) {

}
