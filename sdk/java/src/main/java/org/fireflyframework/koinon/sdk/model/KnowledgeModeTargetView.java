// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KnowledgeModeTargetView contract. */
public record KnowledgeModeTargetView(
    @JsonProperty("id") String id,
    @JsonProperty("kind") KnowledgeModeTargetViewKind kind,
    @JsonProperty("catalog_id") String catalogId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("status") KnowledgeModeTargetViewStatus status,
    @JsonProperty("error_code") String errorCode,
    @JsonProperty("message") String message,
    @JsonProperty("action") KnowledgeModeTargetViewAction action,
    @JsonProperty("index_id") String indexId,
    @JsonProperty("job_id") String jobId,
    @JsonProperty("job_status") String jobStatus,
    @JsonProperty("index_recovery") KnowledgeModeIndexRecovery indexRecovery,
    @JsonProperty("lease_until") String leaseUntil,
    @JsonProperty("source_version_id") String sourceVersionId,
    @JsonProperty("ingestion_extraction_id") String ingestionExtractionId,
    @JsonProperty("view_extraction_id") String viewExtractionId,
    @JsonProperty("raw_sha256") String rawSha256,
    @JsonProperty("raw_bytes") Long rawBytes,
    @JsonProperty("normalized_sha256") String normalizedSha256,
    @JsonProperty("parts") Long parts,
    @JsonProperty("text_bytes") Long textBytes
) {

}
