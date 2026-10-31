// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;



/** Typed canonical ExternalFileReviewView contract. */
public record ExternalFileReviewView(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("revision") Long revision,
    @JsonProperty("authorization_digest") String authorizationDigest,
    @JsonProperty("status") ExternalFileReviewViewStatus status,
    @JsonProperty("filename") String filename,
    @JsonProperty("content_type") String contentType,
    @JsonProperty("mode") AddKnowledgeMode mode,
    @JsonProperty("size_bytes") Long sizeBytes,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("destination") KnowledgeDestination destination,
    @JsonProperty("received_chunks") Long receivedChunks,
    @JsonProperty("total_chunks") Long totalChunks,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("submitted_by") String submittedBy,
    @JsonProperty("credential_id") String credentialId,
    @JsonProperty("application_id") String applicationId,
    @JsonProperty("origin") ExternalFileReviewViewOrigin origin,
    @JsonProperty("authority") ExternalFileReviewViewAuthority authority,
    @JsonProperty("provider") JsonNode provider,
    @JsonProperty("model") JsonNode model,
    @JsonProperty("source_id") String sourceId,
    @JsonProperty("intake_status") String intakeStatus,
    @JsonProperty("receipt") ExternalFileReceipt receipt
) {
    public ExternalFileReviewView {
        provider=ModelValues.json(provider);
        model=ModelValues.json(model);
    }
    @Override public JsonNode provider(){return ModelValues.json(provider);}
    @Override public JsonNode model(){return ModelValues.json(model);}
}
