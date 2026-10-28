// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical NativeReadReceipt contract. */
public record NativeReadReceipt(
    @JsonProperty("result_id") String resultId,
    @JsonProperty("generation_id") String generationId,
    @JsonProperty("stage") String stage,
    @JsonProperty("domain") NativeReadReceiptDomain domain,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("entity_id") String entityId,
    @JsonProperty("content_sha256") String contentSha256,
    @JsonProperty("source_ids") List<String> sourceIds,
    @JsonProperty("snapshot_ids") List<String> snapshotIds,
    @JsonProperty("engine") String engine,
    @JsonProperty("database") String database,
    @JsonProperty("catalog") String catalog,
    @JsonProperty("schema") String schema,
    @JsonProperty("read_kind") NativeReadReceiptReadKind readKind,
    @JsonProperty("origin") NativeReadOrigin origin,
    @JsonProperty("source_version_id") String sourceVersionId,
    @JsonProperty("extraction_id") String extractionId,
    @JsonProperty("knowledge_item_id") String knowledgeItemId,
    @JsonProperty("knowledge_version_id") String knowledgeVersionId,
    @JsonProperty("knowledge_version") Long knowledgeVersion
) {
    public NativeReadReceipt {
        sourceIds=sourceIds==null?null:List.copyOf(sourceIds);
        snapshotIds=snapshotIds==null?null:List.copyOf(snapshotIds);
    }

}
