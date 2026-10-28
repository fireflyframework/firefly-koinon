// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OpenUIArtifact contract. */
public record OpenUIArtifact(
    @JsonProperty("id") String id,
    @JsonProperty("kind") OpenUIArtifactKind kind,
    @JsonProperty("language") String language,
    @JsonProperty("complete") Boolean complete,
    @JsonProperty("run_id") String runId
) {

}
