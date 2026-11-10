// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical KnowledgeModeRecoveryReceipt contract. */
public record KnowledgeModeRecoveryReceipt(
    @JsonProperty("index_id") String indexId,
    @JsonProperty("job_id") String jobId,
    @JsonProperty("state") KnowledgeModeIndexRecoveryState state,
    @JsonProperty("activation_job_id") String activationJobId,
    @JsonProperty("activation_lease_until") String activationLeaseUntil,
    @JsonProperty("index_status") String indexStatus,
    @JsonProperty("native_pointer_state") KnowledgeModeIndexRecoveryNativePointerState nativePointerState,
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("expected_active_id") String expectedActiveId,
    @JsonProperty("expected_connection_revision") Long expectedConnectionRevision,
    @JsonProperty("actions") List<IndexActivateInputRecovery> actions,
    @JsonProperty("message") String message,
    @JsonProperty("receipt_id") String receiptId,
    @JsonProperty("attempt_revision") Long attemptRevision,
    @JsonProperty("resolution_revision") Long resolutionRevision,
    @JsonProperty("resolution") KnowledgeModeRecoveryReceiptResolution resolution,
    @JsonProperty("native_index_id") String nativeIndexId,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("model_id") String modelId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("native_workspace_id") String nativeWorkspaceId
) {
    public KnowledgeModeRecoveryReceipt {
        actions=actions==null?null:List.copyOf(actions);
    }

}
