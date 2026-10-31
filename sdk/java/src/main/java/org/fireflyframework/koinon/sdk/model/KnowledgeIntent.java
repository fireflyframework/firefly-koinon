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
    @JsonProperty("remembered_context_present") Boolean rememberedContextPresent,
    @JsonProperty("status") ExternalReviewViewStatus status,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("receipt") KnowledgeCommitReceipt receipt
) {
    public KnowledgeIntent(String id, Long revision, String tenantId, String ownerSubject, ExternalReviewInputAction action, KnowledgeDestination destination, String targetItemId, Long expectedVersion, KnowledgeContent before, KnowledgeContent after, List<KnowledgeEvidence> evidence, String authorizationDigest, ExternalReviewViewStatus status, Instant createdAt, Instant expiresAt, KnowledgeCommitReceipt receipt){this(id,revision,tenantId,ownerSubject,action,destination,targetItemId,expectedVersion,before,after,evidence,authorizationDigest,null,status,createdAt,expiresAt,receipt);}
    public KnowledgeIntent {
        evidence=evidence==null?null:List.copyOf(evidence);
    }

}
