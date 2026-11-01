// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ProjectActivity contract. */
public record ProjectActivity(
    @JsonProperty("project_id") String projectId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("name") String name,
    @JsonProperty("knowledge") KnowledgeActivityCounts knowledge
) {

}
