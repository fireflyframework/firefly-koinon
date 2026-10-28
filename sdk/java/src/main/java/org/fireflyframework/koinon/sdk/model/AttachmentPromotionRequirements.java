// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AttachmentPromotionRequirements contract. */
public record AttachmentPromotionRequirements(
    @JsonProperty("ready_attachment") Boolean readyAttachment,
    @JsonProperty("ingest_write") Boolean ingestWrite,
    @JsonProperty("catalog_write") Boolean catalogWrite,
    @JsonProperty("document_sha256") Boolean documentSha256,
    @JsonProperty("document_chunk_invalidation_acknowledgement") Boolean documentChunkInvalidationAcknowledgement,
    @JsonProperty("table_snapshot_id") Boolean tableSnapshotId
) {

}
