// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical KnowledgeCommitReceipt contract. */
public record KnowledgeCommitReceipt(
    @JsonProperty("operation_id") String operationId,
    @JsonProperty("intent_id") String intentId,
    @JsonProperty("intent_revision") Long intentRevision,
    @JsonProperty("authorization_digest") String authorizationDigest,
    @JsonProperty("item_id") String itemId,
    @JsonProperty("native_item_id") String nativeItemId,
    @JsonProperty("native_version_id") String nativeVersionId,
    @JsonProperty("version") Long version,
    @JsonProperty("serving_version") Long servingVersion,
    @JsonProperty("action") ExternalReviewInputAction action,
    @JsonProperty("content_sha256") String contentSha256,
    @JsonProperty("evidence_sha256") String evidenceSha256,
    @JsonProperty("committed_at") Instant committedAt,
    @JsonProperty("retrieval_state") KnowledgeCommitReceiptRetrievalState retrievalState,
    @JsonProperty("reason") String reason
) {

}
