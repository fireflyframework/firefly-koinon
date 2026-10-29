// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical StructuredKnowledgeCapabilities contract. */
public record StructuredKnowledgeCapabilities(
    @JsonProperty("bounds") StructuredKnowledgeBounds bounds
) {

    public static StructuredKnowledgeCapabilities empty(){return new StructuredKnowledgeCapabilities(null);}
    public StructuredKnowledgeCapabilities withBounds(StructuredKnowledgeBounds value){return new StructuredKnowledgeCapabilities(value);}
}
