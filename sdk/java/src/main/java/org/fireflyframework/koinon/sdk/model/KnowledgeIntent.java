// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical KnowledgeIntent contract. */
public record KnowledgeIntent(
    @JsonProperty("id") String id,
    @JsonProperty("revision") Long revision,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("owner_subject") String ownerSubject,
    @JsonProperty("action") ExternalReviewInputAction action,
    @JsonProperty("destination") KnowledgeDestination destination,
    @JsonProperty("target_item_id") String targetItemId,
    @JsonProperty("expected_version") Long expectedVersion,
    @JsonProperty("before") KnowledgeContent before,
    @JsonProperty("after") KnowledgeContent after,
    @JsonProperty("evidence") List<KnowledgeEvidence> evidence,
    @JsonProperty("authorization_digest") String authorizationDigest,
    @JsonProperty("status") ExternalReviewViewStatus status,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("receipt") KnowledgeCommitReceipt receipt
) {
    public KnowledgeIntent {
        evidence=evidence==null?null:List.copyOf(evidence);
    }

}
