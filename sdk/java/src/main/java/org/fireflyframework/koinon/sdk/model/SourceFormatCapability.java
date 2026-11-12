// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceFormatCapability contract. */
public record SourceFormatCapability(
    @JsonProperty("extension") String extension,
    @JsonProperty("mode") AddKnowledgeMode mode
) {

}
