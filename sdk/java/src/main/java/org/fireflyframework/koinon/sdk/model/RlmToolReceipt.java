// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical RlmToolReceipt contract. */
public record RlmToolReceipt(
    @JsonProperty("result_id") String resultId,
    @JsonProperty("generation_id") String generationId,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("source_ids") List<String> sourceIds,
    @JsonProperty("knowledge_item_ids") List<String> knowledgeItemIds,
    @JsonProperty("tool_call_id") String toolCallId,
    @JsonProperty("tool_name") RlmToolReceiptToolName toolName,
    @JsonProperty("request_sha256") String requestSha256,
    @JsonProperty("schema_sha256") String schemaSha256,
    @JsonProperty("arguments_sha256") String argumentsSha256,
    @JsonProperty("result_sha256") String resultSha256,
    @JsonProperty("result_kind") RlmToolReceiptResultKind resultKind,
    @JsonProperty("execution_sha256") String executionSha256,
    @JsonProperty("outcome") RlmToolReceiptOutcome outcome,
    @JsonProperty("execution_status") String executionStatus,
    @JsonProperty("execution_state") String executionState
) {
    public RlmToolReceipt(String resultId, String generationId, String tenantId, String workspaceId, List<String> sourceIds, String toolCallId, RlmToolReceiptToolName toolName, String requestSha256, String schemaSha256, String argumentsSha256, String resultSha256, RlmToolReceiptResultKind resultKind, String executionSha256, RlmToolReceiptOutcome outcome, String executionStatus, String executionState){this(resultId,generationId,tenantId,workspaceId,sourceIds,List.of(),toolCallId,toolName,requestSha256,schemaSha256,argumentsSha256,resultSha256,resultKind,executionSha256,outcome,executionStatus,executionState);}
    public RlmToolReceipt {
        sourceIds=sourceIds==null?List.of():List.copyOf(sourceIds);
        knowledgeItemIds=knowledgeItemIds==null?List.of():List.copyOf(knowledgeItemIds);
    }

}
