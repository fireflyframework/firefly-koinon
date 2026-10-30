// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ExternalFileCleanupReview contract. */
public record ExternalFileCleanupReview(
    @JsonProperty("id") String id,
    @JsonProperty("status") ExternalFileCleanupReviewStatus status,
    @JsonProperty("processed_objects") Integer processedObjects,
    @JsonProperty("total_objects") Integer totalObjects
) {

}
