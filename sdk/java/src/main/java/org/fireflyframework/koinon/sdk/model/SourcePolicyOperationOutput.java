// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical SourcePolicyOperationOutput contract. */
public record SourcePolicyOperationOutput(
    @JsonProperty("schema") SourcePolicyOperationOutputSchema schema,
    @JsonProperty("receipt_id") String receiptId,
    @JsonProperty("operation_id") String operationId,
    @JsonProperty("action") SourcePolicyOperationOutputAction action,
    @JsonProperty("mapping_id") String mappingId,
    @JsonProperty("policy_id") String policyId,
    @JsonProperty("expected_policy_revision") Long expectedPolicyRevision,
    @JsonProperty("result_policy_revision") Long resultPolicyRevision,
    @JsonProperty("review_digest") String reviewDigest,
    @JsonProperty("review_expires_at") Instant reviewExpiresAt,
    @JsonProperty("disposition") SourcePolicyOperationOutputDisposition disposition
) {

}
