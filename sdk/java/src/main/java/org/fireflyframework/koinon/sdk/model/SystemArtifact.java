// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SystemArtifact contract. */
public record SystemArtifact(
    @JsonProperty("component") SystemArtifactComponent component,
    @JsonProperty("kind") SystemArtifactKind kind,
    @JsonProperty("present") Boolean present,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("content_type") SystemArtifactContentType contentType
) {

}
