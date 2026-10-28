// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical AttachmentHistorySummary contract. */
public record AttachmentHistorySummary(
    @JsonProperty("id") String id,
    @JsonProperty("filename") String filename,
    @JsonProperty("media_type") String mediaType,
    @JsonProperty("kind") AttachmentFormatKind kind,
    @JsonProperty("size_bytes") Long sizeBytes,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("status") AttachmentHistorySummaryStatus status,
    @JsonProperty("revision") Long revision,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("available") Boolean available
) {

}
