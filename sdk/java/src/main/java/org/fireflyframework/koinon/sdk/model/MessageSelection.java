// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical MessageSelection contract. */
public record MessageSelection(
    @JsonProperty("thread_id") String threadId,
    @JsonProperty("message_ids") List<String> messageIds
) {
    public MessageSelection {
        messageIds=messageIds==null?null:List.copyOf(messageIds);
    }

    public static MessageSelection empty(){return new MessageSelection(null,null);}
    public MessageSelection withThreadId(String value){return new MessageSelection(value,messageIds);}
    public MessageSelection withMessageIds(List<String> value){return new MessageSelection(threadId,value);}
}
