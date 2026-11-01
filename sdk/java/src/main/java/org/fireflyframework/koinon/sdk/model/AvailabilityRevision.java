// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AvailabilityRevision contract. */
public record AvailabilityRevision(
    @JsonProperty("source_version_id") String sourceVersionId,
    @JsonProperty("extraction_id") String extractionId,
    @JsonProperty("snapshot_id") String snapshotId,
    @JsonProperty("active_index_id") String activeIndexId
) {

}
