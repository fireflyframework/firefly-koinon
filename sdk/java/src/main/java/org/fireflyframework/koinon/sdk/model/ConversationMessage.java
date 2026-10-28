// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical ConversationMessage contract. */
public record ConversationMessage(
    @JsonProperty("id") String id,
    @JsonProperty("role") ChatMessageRole role,
    @JsonProperty("text") String text,
    @JsonProperty("status") ConversationMessageStatus status,
    @JsonProperty("revision") String revision,
    @JsonProperty("private_derived") Boolean privateDerived,
    @JsonProperty("source_ids") List<String> sourceIds,
    @JsonProperty("result_ids") List<String> resultIds,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("presentation") EvidencePresentation presentation
) {
    public ConversationMessage {
        sourceIds=sourceIds==null?null:List.copyOf(sourceIds);
        resultIds=resultIds==null?null:List.copyOf(resultIds);
    }

}
