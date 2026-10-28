// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical ChatFolder contract. */
public record ChatFolder(
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("parent_id") String parentId,
    @JsonProperty("scope") KnowledgeScope scope,
    @JsonProperty("revision") Long revision,
    @JsonProperty("conversation_count") Long conversationCount,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("updated_at") Instant updatedAt
) {

}
