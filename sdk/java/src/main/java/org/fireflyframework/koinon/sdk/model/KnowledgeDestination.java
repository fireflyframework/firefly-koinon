// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KnowledgeDestination contract. */
public record KnowledgeDestination(
    @JsonProperty("id") String id,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("project_id") String projectId,
    @JsonProperty("name") String name,
    @JsonProperty("ancestry_digest") String ancestryDigest
) {

}
