// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical StructuredEvidence contract. */
public record StructuredEvidence(
    @JsonProperty("kind") StructuredEvidenceKind kind,
    @JsonProperty("source") SourceReference source
) implements KnowledgeEvidence {

}
