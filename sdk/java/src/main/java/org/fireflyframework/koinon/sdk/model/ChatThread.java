// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical ChatThread contract. */
public record ChatThread(
    @JsonProperty("revision") Long revision,
    @JsonProperty("title_source") ChatThreadTitleSource titleSource,
    @JsonProperty("folder_id") String folderId,
    @JsonProperty("archived_at") String archivedAt,
    @JsonProperty("id") String id,
    @JsonProperty("title") String title,
    @JsonProperty("scope") KnowledgeScope scope,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("updated_at") Instant updatedAt
) {

}
