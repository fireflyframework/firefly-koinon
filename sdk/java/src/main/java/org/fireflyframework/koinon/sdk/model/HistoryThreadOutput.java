// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical HistoryThreadOutput contract. */
public record HistoryThreadOutput(
    @JsonProperty("id") String id,
    @JsonProperty("title") String title,
    @JsonProperty("title_source") ChatThreadTitleSource titleSource,
    @JsonProperty("revision") Long revision,
    @JsonProperty("folder_id") String folderId,
    @JsonProperty("archived_at") Instant archivedAt,
    @JsonProperty("scope") KnowledgeScope scope,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("updated_at") Instant updatedAt
) {

}
