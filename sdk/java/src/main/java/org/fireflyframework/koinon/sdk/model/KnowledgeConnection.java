// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;



/** Typed canonical KnowledgeConnection contract. */
public record KnowledgeConnection(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("domain") KnowledgeDomain domain,
    @JsonProperty("role") String role,
    @JsonProperty("mode") ConnectionMode mode,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("model_id") String modelId,
    @JsonProperty("model_options") JsonNode modelOptions,
    @JsonProperty("dimensions") Long dimensions,
    @JsonProperty("storage_dimensions") Long storageDimensions,
    @JsonProperty("space_id") String spaceId,
    @JsonProperty("embedding_fingerprint") String embeddingFingerprint,
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("revision") Long revision,
    @JsonProperty("created_by") String createdBy,
    @JsonProperty("updated_by") String updatedBy,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("updated_at") Instant updatedAt
) {
    public KnowledgeConnection {
        modelOptions=ModelValues.json(modelOptions);
    }
    @Override public JsonNode modelOptions(){return ModelValues.json(modelOptions);}
}
