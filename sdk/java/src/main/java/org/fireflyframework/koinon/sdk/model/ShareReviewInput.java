// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ShareReviewInput contract. */
public record ShareReviewInput(
    @JsonProperty("thread_id") String threadId,
    @JsonProperty("message_ids") List<String> messageIds
) {
    public ShareReviewInput {
        messageIds=messageIds==null?null:List.copyOf(messageIds);
    }

    public static ShareReviewInput empty(){return new ShareReviewInput(null,null);}
    public ShareReviewInput withThreadId(String value){return new ShareReviewInput(value,messageIds);}
    public ShareReviewInput withMessageIds(List<String> value){return new ShareReviewInput(threadId,value);}
}
