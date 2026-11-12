// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical SourceReviewPage contract. */
public record SourceReviewPage(
    @JsonProperty("review_id") String reviewId,
    @JsonProperty("validation_id") String validationId,
    @JsonProperty("root_kind") SourceReviewPageRootKind rootKind,
    @JsonProperty("policy_revision") Long policyRevision,
    @JsonProperty("review_digest") String reviewDigest,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("items") List<SourcePreviewItem> items,
    @JsonProperty("next_cursor") String nextCursor,
    @JsonProperty("enumeration_complete") Boolean enumerationComplete,
    @JsonProperty("total") Long total,
    @JsonProperty("observed_count") Long observedCount,
    @JsonProperty("known_bytes") Long knownBytes,
    @JsonProperty("unknown_size_count") Long unknownSizeCount,
    @JsonProperty("can_apply") Boolean canApply,
    @JsonProperty("destination") SourceDestinationPresentation destination
) {
    public SourceReviewPage {
        items=items==null?null:List.copyOf(items);
    }

}
