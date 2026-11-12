// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceMappingPresentation contract. */
public record SourceMappingPresentation(
    @JsonProperty("source_root") SourceRootPresentation sourceRoot,
    @JsonProperty("destination") SourceDestinationPresentation destination,
    @JsonProperty("unavailable_reason") SourceMappingPresentationUnavailableReason unavailableReason
) {

}
