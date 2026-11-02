// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical FileRecoveryView contract. */
public record FileRecoveryView(
    @JsonProperty("batch_id") String batchId,
    @JsonProperty("item_id") String itemId,
    @JsonProperty("batch_revision") Integer batchRevision,
    @JsonProperty("native_state") FileRecoveryViewNativeState nativeState,
    @JsonProperty("operation") BulkRecoveryActionOperation operation,
    @JsonProperty("reason_code") String reasonCode,
    @JsonProperty("attempts") Integer attempts,
    @JsonProperty("max_attempts") Integer maxAttempts,
    @JsonProperty("checked_at") Instant checkedAt,
    @JsonProperty("job_status") FileRecoveryViewJobStatus jobStatus,
    @JsonProperty("original_receipt_state") FileRecoveryViewOriginalReceiptState originalReceiptState
) {

}
