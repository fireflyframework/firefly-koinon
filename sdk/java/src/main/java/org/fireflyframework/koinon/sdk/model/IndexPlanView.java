// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical IndexPlanView contract. */
public record IndexPlanView(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("domain") KnowledgeDomain domain,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("provider_kind") String providerKind,
    @JsonProperty("provider_revision") Long providerRevision,
    @JsonProperty("model_id") String modelId,
    @JsonProperty("dimensions") Long dimensions,
    @JsonProperty("storage_dimensions") Long storageDimensions,
    @JsonProperty("qualification") String qualification,
    @JsonProperty("expected_connection_revision") Long expectedConnectionRevision,
    @JsonProperty("active_space_id") String activeSpaceId,
    @JsonProperty("active_index_id") String activeIndexId,
    @JsonProperty("chunk_count") Long chunkCount,
    @JsonProperty("warnings") List<String> warnings
) {
    public IndexPlanView {
        warnings=warnings==null?null:List.copyOf(warnings);
    }

}
