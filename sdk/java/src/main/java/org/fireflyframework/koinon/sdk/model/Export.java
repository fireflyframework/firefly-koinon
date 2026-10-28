// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical Export contract. */
public record Export(
    @JsonProperty("id") String id,
    @JsonProperty("kind") ExportKind kind,
    @JsonProperty("format") ExportFormat format,
    @JsonProperty("title") String title,
    @JsonProperty("status") ExportStatus status,
    @JsonProperty("revision") String revision,
    @JsonProperty("completeness") ExportCompleteness completeness,
    @JsonProperty("row_count") Long rowCount,
    @JsonProperty("truncated") Boolean truncated,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("expires_at") Instant expiresAt
) {

}
