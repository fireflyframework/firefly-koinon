// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;

@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, include = JsonTypeInfo.As.PROPERTY, property = "kind")
@JsonSubTypes({
  @JsonSubTypes.Type(value = SearchEvidence.class, name = "search"),
  @JsonSubTypes.Type(value = QueryEvidence.class, name = "query"),
  @JsonSubTypes.Type(value = SchemaEvidence.class, name = "schema"),
  @JsonSubTypes.Type(value = LineageEvidence.class, name = "lineage"),
  @JsonSubTypes.Type(value = PrivateAttachmentEvidence.class, name = "attachment"),
  @JsonSubTypes.Type(value = CatalogProposalEvidence.class, name = "proposal")
})
public sealed interface EvidenceResult
    permits SearchEvidence,
        QueryEvidence,
        SchemaEvidence,
        LineageEvidence,
        PrivateAttachmentEvidence,
        CatalogProposalEvidence {
  String id();

  String runId();

  EvidenceKind kind();
}
