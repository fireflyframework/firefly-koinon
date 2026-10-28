// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical KnowledgeRole contract. */
public record KnowledgeRole(
    @JsonProperty("id") String id,
    @JsonProperty("domain") KnowledgeDomain domain,
    @JsonProperty("label") String label,
    @JsonProperty("kind") RoleKind kind,
    @JsonProperty("purposes") List<String> purposes,
    @JsonProperty("supports_current_agent") Boolean supportsCurrentAgent,
    @JsonProperty("compatible_index_required") Boolean compatibleIndexRequired,
    @JsonProperty("assignment") KnowledgeRoleAssignment assignment,
    @JsonProperty("status") KnowledgeRoleStatus status,
    @JsonProperty("runtime_qualification") KnowledgeRoleRuntimeQualification runtimeQualification
) {
    public KnowledgeRole {
        purposes=purposes==null?null:List.copyOf(purposes);
    }

}
