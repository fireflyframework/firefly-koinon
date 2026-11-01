// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SystemComponentVersion contract. */
public record SystemComponentVersion(
    @JsonProperty("id") SystemArtifactComponent id,
    @JsonProperty("distribution") SystemComponentVersionDistribution distribution,
    @JsonProperty("version") String version,
    @JsonProperty("available") Boolean available
) {

}
