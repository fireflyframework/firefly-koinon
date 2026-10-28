// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical KnowledgeIndexView contract. */
public record KnowledgeIndexView(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("domain") KnowledgeDomain domain,
    @JsonProperty("native_id") String nativeId,
    @JsonProperty("space_id") String spaceId,
    @JsonProperty("provider_kind") String providerKind,
    @JsonProperty("model_id") String modelId,
    @JsonProperty("dimensions") Long dimensions,
    @JsonProperty("storage_dimensions") Long storageDimensions,
    @JsonProperty("status") String status,
    @JsonProperty("active") Boolean active,
    @JsonProperty("revision") Long revision,
    @JsonProperty("job_id") String jobId,
    @JsonProperty("chunk_count") Long chunkCount,
    @JsonProperty("vector_count") Long vectorCount,
    @JsonProperty("indexed") Boolean indexed,
    @JsonProperty("qualification") String qualification,
    @JsonProperty("recovery_required") Boolean recoveryRequired,
    @JsonProperty("native_status") String nativeStatus,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("created_by") String createdBy,
    @JsonProperty("updated_by") String updatedBy,
    @JsonProperty("previous_space_id") String previousSpaceId,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("ready_at") String readyAt,
    @JsonProperty("activated_at") String activatedAt,
    @JsonProperty("retired_at") String retiredAt,
    @JsonProperty("error_code") String errorCode,
    @JsonProperty("error") String error
) {

}
