// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical DeploymentStorage contract. */
public record DeploymentStorage(
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("available") Boolean available,
    @JsonProperty("status") ObservationStatus status,
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("reason") String reason,
    @JsonProperty("ownership") DeploymentConfigurationOwnership ownership,
    @JsonProperty("read_only") Boolean readOnly,
    @JsonProperty("id") KnowledgeDomain id,
    @JsonProperty("backend") String backend,
    @JsonProperty("store_originals") Boolean storeOriginals
) {

}
