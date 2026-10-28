// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ConversationOrigin contract. */
public record ConversationOrigin(
    @JsonProperty("kind") ConversationExportInputKind kind,
    @JsonProperty("thread_id") String threadId,
    @JsonProperty("message_ids") List<String> messageIds
) implements KnowledgeOrigin {
    public ConversationOrigin {
        messageIds=messageIds==null?null:List.copyOf(messageIds);
    }

}
