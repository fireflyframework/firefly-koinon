// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;



/** Typed canonical ConnectionPool contract. */
public record ConnectionPool(
    @JsonProperty("size") Long size,
    @JsonProperty("max_overflow") Long maxOverflow,
    @JsonProperty("timeout") BigDecimal timeout,
    @JsonProperty("recycle") Long recycle,
    @JsonProperty("pre_ping") Boolean prePing
) {

}
