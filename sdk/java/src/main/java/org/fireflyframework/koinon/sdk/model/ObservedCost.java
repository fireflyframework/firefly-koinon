// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;



/** Typed canonical ObservedCost contract. */
public record ObservedCost(
    @JsonProperty("amount") BigDecimal amount,
    @JsonProperty("currency") String currency,
    @JsonProperty("status") ObservedCostStatus status,
    @JsonProperty("source") String source,
    @JsonProperty("reason") String reason
) {

}
