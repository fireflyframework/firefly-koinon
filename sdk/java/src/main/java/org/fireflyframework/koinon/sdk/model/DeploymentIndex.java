// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical DeploymentIndex contract. */
public record DeploymentIndex(
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("available") Boolean available,
    @JsonProperty("status") ObservationStatus status,
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("reason") String reason,
    @JsonProperty("id") String id,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("vector_extension") Boolean vectorExtension,
    @JsonProperty("embedding_sets") Long embeddingSets,
    @JsonProperty("physical_indexes") Long physicalIndexes
) {

}
