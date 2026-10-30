// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DocumentPartContent contract. */
public record DocumentPartContent(
    @JsonProperty("document_id") String documentId,
    @JsonProperty("catalog_source_id") String catalogSourceId,
    @JsonProperty("native_source_id") String nativeSourceId,
    @JsonProperty("source_version_id") String sourceVersionId,
    @JsonProperty("extraction_id") String extractionId,
    @JsonProperty("source_part_id") String sourcePartId,
    @JsonProperty("kind") DocumentPartContentKind kind,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("text") String text,
    @JsonProperty("recorded_page") Long recordedPage,
    @JsonProperty("page_basis") SourceReferencePageBasis pageBasis,
    @JsonProperty("raw_sha256") String rawSha256,
    @JsonProperty("normalized_sha256") String normalizedSha256,
    @JsonProperty("input_sha256") String inputSha256
) {

}
