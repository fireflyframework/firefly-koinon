// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceControlOutput contract. */
public record SourceControlOutput(
    @JsonProperty("operation_id") String operationId,
    @JsonProperty("receipt_id") String receiptId,
    @JsonProperty("action") SourceControlOutputAction action,
    @JsonProperty("control_revision") Long controlRevision,
    @JsonProperty("run_id") String runId,
    @JsonProperty("disposition") SourceControlOutputDisposition disposition
) {

}
