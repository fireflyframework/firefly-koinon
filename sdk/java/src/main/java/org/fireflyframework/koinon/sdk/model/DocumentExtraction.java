// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical DocumentExtraction contract. */
public record DocumentExtraction(
    @JsonProperty("document_id") String documentId,
    @JsonProperty("catalog_source_id") String catalogSourceId,
    @JsonProperty("native_source_id") String nativeSourceId,
    @JsonProperty("source_version_id") String sourceVersionId,
    @JsonProperty("extraction_id") String extractionId,
    @JsonProperty("purpose") String purpose,
    @JsonProperty("coverage") String coverage,
    @JsonProperty("normalized_sha256") String normalizedSha256,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("predecessor_extraction_id") String predecessorExtractionId
) {

}
