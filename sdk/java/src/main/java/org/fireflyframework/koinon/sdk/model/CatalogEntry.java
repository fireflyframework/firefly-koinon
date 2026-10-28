// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;



/** Typed canonical CatalogEntry contract. */
public record CatalogEntry(
    @JsonProperty("created_by") String createdBy,
    @JsonProperty("updated_by") String updatedBy,
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("kind") String kind,
    @JsonProperty("name") String name,
    @JsonProperty("parent_id") String parentId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("project_id") String projectId,
    @JsonProperty("description") String description,
    @JsonProperty("status") String status,
    @JsonProperty("metadata") JsonNode metadata,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("updated_at") Instant updatedAt
) {
    public CatalogEntry {
        metadata=ModelValues.json(metadata);
    }
    @Override public JsonNode metadata(){return ModelValues.json(metadata);}
}
