// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KnowledgeItemView contract. */
public record KnowledgeItemView(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("project_id") String projectId,
    @JsonProperty("destination_id") String destinationId,
    @JsonProperty("head_version") Long headVersion,
    @JsonProperty("serving_version") Long servingVersion,
    @JsonProperty("selected_version") KnowledgeVersionView selectedVersion
) {

}
