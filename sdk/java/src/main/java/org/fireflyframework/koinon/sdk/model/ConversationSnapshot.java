// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ConversationSnapshot contract. */
public record ConversationSnapshot(
    @JsonProperty("thread_id") String threadId,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("owner_subject") String ownerSubject,
    @JsonProperty("title") String title,
    @JsonProperty("revision") String revision,
    @JsonProperty("messages") List<ConversationMessage> messages,
    @JsonProperty("sources") List<SourceReference> sources,
    @JsonProperty("source_manifest_complete") Boolean sourceManifestComplete,
    @JsonProperty("originating_token_ids") List<String> originatingTokenIds
) {
    public ConversationSnapshot {
        messages=messages==null?null:List.copyOf(messages);
        sources=sources==null?null:List.copyOf(sources);
        originatingTokenIds=originatingTokenIds==null?null:List.copyOf(originatingTokenIds);
    }

}
