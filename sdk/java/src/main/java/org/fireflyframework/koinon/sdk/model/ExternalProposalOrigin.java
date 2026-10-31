// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ExternalProposalOrigin contract. */
public record ExternalProposalOrigin(
    @JsonProperty("kind") ExternalFileReviewViewOrigin kind,
    @JsonProperty("source_receipt_ids") List<String> sourceReceiptIds
) implements KnowledgeOrigin {
    public ExternalProposalOrigin {
        sourceReceiptIds=sourceReceiptIds==null?null:List.copyOf(sourceReceiptIds);
    }

}
