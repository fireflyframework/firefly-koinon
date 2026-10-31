// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical QueryBatchResult contract. */
public record QueryBatchResult(
    @JsonProperty("batch_id") String batchId,
    @JsonProperty("item_id") String itemId,
    @JsonProperty("status") QueryBatchItemViewStatus status,
    @JsonProperty("result") BatchQueryOutcome result,
    @JsonProperty("error_code") String errorCode
) {

}
