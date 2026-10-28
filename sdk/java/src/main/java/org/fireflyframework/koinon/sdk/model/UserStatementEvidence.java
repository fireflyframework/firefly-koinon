// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical UserStatementEvidence contract. */
public record UserStatementEvidence(
    @JsonProperty("kind") UserStatementEvidenceKind kind,
    @JsonProperty("text") String text,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("author_subject") String authorSubject,
    @JsonProperty("recorded_at") Instant recordedAt,
    @JsonProperty("authority") UserStatementEvidenceAuthority authority
) implements KnowledgeEvidence {

}
