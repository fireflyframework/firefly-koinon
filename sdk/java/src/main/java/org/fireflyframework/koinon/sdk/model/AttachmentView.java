// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical AttachmentView contract. */
public record AttachmentView(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("thread_id") String threadId,
    @JsonProperty("filename") String filename,
    @JsonProperty("media_type") String mediaType,
    @JsonProperty("kind") AttachmentFormatKind kind,
    @JsonProperty("size_bytes") Long sizeBytes,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("status") AttachmentHistorySummaryStatus status,
    @JsonProperty("revision") Long revision,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("page_count") Long pageCount,
    @JsonProperty("chunk_count") Long chunkCount,
    @JsonProperty("progress") AttachmentProgress progress,
    @JsonProperty("error_code") String errorCode,
    @JsonProperty("error") String error,
    @JsonProperty("warnings") List<String> warnings
) {
    public AttachmentView {
        warnings=warnings==null?null:List.copyOf(warnings);
    }

}
