// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical DocumentVersion contract. */
public record DocumentVersion(
    @JsonProperty("document_id") String documentId,
    @JsonProperty("catalog_source_id") String catalogSourceId,
    @JsonProperty("native_source_id") String nativeSourceId,
    @JsonProperty("source_version_id") String sourceVersionId,
    @JsonProperty("filename") String filename,
    @JsonProperty("media_type") String mediaType,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("byte_size") Long byteSize,
    @JsonProperty("actor") String actor,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("predecessor_source_version_id") String predecessorSourceVersionId
) {

}
