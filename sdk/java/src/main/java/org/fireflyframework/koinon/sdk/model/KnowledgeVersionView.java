// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical KnowledgeVersionView contract. */
public record KnowledgeVersionView(
    @JsonProperty("item_id") String itemId,
    @JsonProperty("version") Long version,
    @JsonProperty("version_id") String versionId,
    @JsonProperty("publication") KnowledgeVersionViewPublication publication,
    @JsonProperty("serving") Boolean serving,
    @JsonProperty("content") KnowledgeContent content,
    @JsonProperty("evidence") List<KnowledgeEvidence> evidence,
    @JsonProperty("content_sha256") String contentSha256,
    @JsonProperty("evidence_sha256") String evidenceSha256,
    @JsonProperty("operation_id") String operationId,
    @JsonProperty("author_subject") String authorSubject,
    @JsonProperty("committed_at") Instant committedAt
) {
    public KnowledgeVersionView {
        evidence=evidence==null?null:List.copyOf(evidence);
    }

}
