// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical CommittedKnowledge contract. */
public record CommittedKnowledge(
    @JsonProperty("status") CommittedKnowledgeStatus status,
    @JsonProperty("receipt") KnowledgeCommitReceipt receipt
) implements KnowledgeCommitOutcome {

}
