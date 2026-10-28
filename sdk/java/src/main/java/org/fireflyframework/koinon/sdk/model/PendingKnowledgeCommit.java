// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical PendingKnowledgeCommit contract. */
public record PendingKnowledgeCommit(
    @JsonProperty("status") PendingKnowledgeCommitStatus status,
    @JsonProperty("operation_id") String operationId,
    @JsonProperty("intent_id") String intentId,
    @JsonProperty("reason") PendingKnowledgeCommitReason reason
) implements KnowledgeCommitOutcome {

}
