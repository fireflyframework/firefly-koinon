// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourcePolicyApplyInput contract. */
public record SourcePolicyApplyInput(
    @JsonProperty("operation_id") String operationId,
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("review_id") String reviewId,
    @JsonProperty("review_digest") String reviewDigest
) {

    public static SourcePolicyApplyInput empty(){return new SourcePolicyApplyInput(null,null,null,null);}
    public SourcePolicyApplyInput withOperationId(String value){return new SourcePolicyApplyInput(value,expectedRevision,reviewId,reviewDigest);}
    public SourcePolicyApplyInput withExpectedRevision(Integer value){return new SourcePolicyApplyInput(operationId,value,reviewId,reviewDigest);}
    public SourcePolicyApplyInput withReviewId(String value){return new SourcePolicyApplyInput(operationId,expectedRevision,value,reviewDigest);}
    public SourcePolicyApplyInput withReviewDigest(String value){return new SourcePolicyApplyInput(operationId,expectedRevision,reviewId,value);}
}
