// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceReference contract. */
public record SourceReference(
    @JsonProperty("id") String id,
    @JsonProperty("asset_id") String assetId,
    @JsonProperty("source_id") String sourceId,
    @JsonProperty("title") String title,
    @JsonProperty("kind") SourceReferenceKind kind,
    @JsonProperty("knowledge_item_id") String knowledgeItemId,
    @JsonProperty("knowledge_version_id") String knowledgeVersionId,
    @JsonProperty("knowledge_version") Long knowledgeVersion,
    @JsonProperty("source_version_id") String sourceVersionId,
    @JsonProperty("extraction_id") String extractionId,
    @JsonProperty("source_part_id") String sourcePartId,
    @JsonProperty("source_part_sha256") String sourcePartSha256,
    @JsonProperty("recorded_page") Long recordedPage,
    @JsonProperty("page_basis") SourceReferencePageBasis pageBasis,
    @JsonProperty("used_revision") String usedRevision,
    @JsonProperty("snapshot_id") String snapshotId,
    @JsonProperty("query_id") String queryId,
    @JsonProperty("chunk_id") String chunkId,
    @JsonProperty("page") Long page,
    @JsonProperty("section") String section,
    @JsonProperty("quote") String quote,
    @JsonProperty("current_revision") String currentRevision,
    @JsonProperty("availability") SourceReferenceAvailability availability
) {

}
