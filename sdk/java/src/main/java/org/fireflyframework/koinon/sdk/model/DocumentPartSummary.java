// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical DocumentPartSummary contract. */
public record DocumentPartSummary(
    @JsonProperty("document_id") String documentId,
    @JsonProperty("catalog_source_id") String catalogSourceId,
    @JsonProperty("native_source_id") String nativeSourceId,
    @JsonProperty("source_version_id") String sourceVersionId,
    @JsonProperty("extraction_id") String extractionId,
    @JsonProperty("source_part_id") String sourcePartId,
    @JsonProperty("kind") DocumentPartSummaryKind kind,
    @JsonProperty("ordinal") Long ordinal,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("recorded_page") Long recordedPage,
    @JsonProperty("page_basis") SourceReferencePageBasis pageBasis,
    @JsonProperty("char_start") Long charStart,
    @JsonProperty("char_end") Long charEnd,
    @JsonProperty("offset_basis") String offsetBasis,
    @JsonProperty("created_at") Instant createdAt
) {

}
