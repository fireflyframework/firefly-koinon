// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical RunInput contract. */
public record RunInput(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("attachment_ids") List<String> attachmentIds,
    @JsonProperty("agent_id") String agentId,
    @JsonProperty("message") String message,
    @JsonProperty("scope") JsonField<KnowledgeScope> scope,
    @JsonProperty("client_request_id") String clientRequestId
) {
    public RunInput {
        attachmentIds=attachmentIds==null?null:List.copyOf(attachmentIds);
    }

    public static RunInput empty(){return new RunInput(null,null,null,null,null,null);}
    public RunInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new RunInput(JsonField.of(value),attachmentIds,agentId,message,scope,clientRequestId);}
    public RunInput clearReaderSourceConnections(){return new RunInput(JsonField.clear(),attachmentIds,agentId,message,scope,clientRequestId);}
    public RunInput omitReaderSourceConnections(){return new RunInput(null,attachmentIds,agentId,message,scope,clientRequestId);}
    public RunInput withAttachmentIds(List<String> value){return new RunInput(readerSourceConnections,value,agentId,message,scope,clientRequestId);}
    public RunInput withAgentId(String value){return new RunInput(readerSourceConnections,attachmentIds,value,message,scope,clientRequestId);}
    public RunInput withMessage(String value){return new RunInput(readerSourceConnections,attachmentIds,agentId,value,scope,clientRequestId);}
    public RunInput withScope(KnowledgeScope value){return new RunInput(readerSourceConnections,attachmentIds,agentId,message,JsonField.of(value),clientRequestId);}
    public RunInput clearScope(){return new RunInput(readerSourceConnections,attachmentIds,agentId,message,JsonField.clear(),clientRequestId);}
    public RunInput omitScope(){return new RunInput(readerSourceConnections,attachmentIds,agentId,message,null,clientRequestId);}
    public RunInput withClientRequestId(String value){return new RunInput(readerSourceConnections,attachmentIds,agentId,message,scope,value);}
}
