// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical RunInput contract. */
public record RunInput(
    @JsonProperty("attachment_ids") List<String> attachmentIds,
    @JsonProperty("agent_id") String agentId,
    @JsonProperty("message") String message,
    @JsonProperty("scope") JsonField<KnowledgeScope> scope,
    @JsonProperty("client_request_id") String clientRequestId
) {
    public RunInput {
        attachmentIds=attachmentIds==null?null:List.copyOf(attachmentIds);
    }

    public static RunInput empty(){return new RunInput(null,null,null,null,null);}
    public RunInput withAttachmentIds(List<String> value){return new RunInput(value,agentId,message,scope,clientRequestId);}
    public RunInput withAgentId(String value){return new RunInput(attachmentIds,value,message,scope,clientRequestId);}
    public RunInput withMessage(String value){return new RunInput(attachmentIds,agentId,value,scope,clientRequestId);}
    public RunInput withScope(KnowledgeScope value){return new RunInput(attachmentIds,agentId,message,JsonField.of(value),clientRequestId);}
    public RunInput clearScope(){return new RunInput(attachmentIds,agentId,message,JsonField.clear(),clientRequestId);}
    public RunInput omitScope(){return new RunInput(attachmentIds,agentId,message,null,clientRequestId);}
    public RunInput withClientRequestId(String value){return new RunInput(attachmentIds,agentId,message,scope,value);}
}
