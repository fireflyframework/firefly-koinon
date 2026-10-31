// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DocumentEvidence contract. */
public record DocumentEvidence(
    @JsonProperty("kind") DocumentEvidenceKind kind,
    @JsonProperty("source") SourceReference source,
    @JsonProperty("basis") DocumentEvidenceBasis basis
) implements KnowledgeEvidence {
    public DocumentEvidence(DocumentEvidenceKind kind, SourceReference source){this(kind,source,null);}

}
