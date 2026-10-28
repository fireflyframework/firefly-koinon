// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ConversationExportInput contract. */
public record ConversationExportInput(
    @JsonProperty("thread_id") String threadId,
    @JsonProperty("message_ids") List<String> messageIds,
    @JsonProperty("kind") ConversationExportInputKind kind,
    @JsonProperty("format") ConversationExportInputFormat format,
    @JsonProperty("include_evidence") Boolean includeEvidence
) implements ExportReviewRequest {
    public ConversationExportInput {
        messageIds=messageIds==null?null:List.copyOf(messageIds);
    }

    public static ConversationExportInput empty(){return new ConversationExportInput(null,null,null,null,null);}
    public ConversationExportInput withThreadId(String value){return new ConversationExportInput(value,messageIds,kind,format,includeEvidence);}
    public ConversationExportInput withMessageIds(List<String> value){return new ConversationExportInput(threadId,value,kind,format,includeEvidence);}
    public ConversationExportInput withKind(ConversationExportInputKind value){return new ConversationExportInput(threadId,messageIds,value,format,includeEvidence);}
    public ConversationExportInput withFormat(ConversationExportInputFormat value){return new ConversationExportInput(threadId,messageIds,kind,value,includeEvidence);}
    public ConversationExportInput withIncludeEvidence(Boolean value){return new ConversationExportInput(threadId,messageIds,kind,format,value);}
}
