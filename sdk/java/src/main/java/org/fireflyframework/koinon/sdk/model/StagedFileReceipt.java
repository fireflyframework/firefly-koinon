// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical StagedFileReceipt contract. */
public record StagedFileReceipt(
    @JsonProperty("receipt_id") String receiptId,
    @JsonProperty("batch_id") String batchId,
    @JsonProperty("item_id") String itemId,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("size_bytes") Long sizeBytes,
    @JsonProperty("status") StagedFileReceiptStatus status
) {

}
