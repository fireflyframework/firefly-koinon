// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IndexCreateInput contract. */
public record IndexCreateInput(
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("domain") KnowledgeDomain domain,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("model_id") String modelId,
    @JsonProperty("expected_dimensions") JsonField<Integer> expectedDimensions,
    @JsonProperty("expected_active_id") JsonField<String> expectedActiveId,
    @JsonProperty("expected_connection_revision") JsonField<Long> expectedConnectionRevision,
    @JsonProperty("batch_size") Integer batchSize
) {

    public static IndexCreateInput empty(){return new IndexCreateInput(null,null,null,null,null,null,null,null);}
    public IndexCreateInput withWorkspaceId(String value){return new IndexCreateInput(value,domain,providerId,modelId,expectedDimensions,expectedActiveId,expectedConnectionRevision,batchSize);}
    public IndexCreateInput withDomain(KnowledgeDomain value){return new IndexCreateInput(workspaceId,value,providerId,modelId,expectedDimensions,expectedActiveId,expectedConnectionRevision,batchSize);}
    public IndexCreateInput withProviderId(String value){return new IndexCreateInput(workspaceId,domain,value,modelId,expectedDimensions,expectedActiveId,expectedConnectionRevision,batchSize);}
    public IndexCreateInput withModelId(String value){return new IndexCreateInput(workspaceId,domain,providerId,value,expectedDimensions,expectedActiveId,expectedConnectionRevision,batchSize);}
    public IndexCreateInput withExpectedDimensions(Integer value){return new IndexCreateInput(workspaceId,domain,providerId,modelId,JsonField.of(value),expectedActiveId,expectedConnectionRevision,batchSize);}
    public IndexCreateInput clearExpectedDimensions(){return new IndexCreateInput(workspaceId,domain,providerId,modelId,JsonField.clear(),expectedActiveId,expectedConnectionRevision,batchSize);}
    public IndexCreateInput omitExpectedDimensions(){return new IndexCreateInput(workspaceId,domain,providerId,modelId,null,expectedActiveId,expectedConnectionRevision,batchSize);}
    public IndexCreateInput withExpectedActiveId(String value){return new IndexCreateInput(workspaceId,domain,providerId,modelId,expectedDimensions,JsonField.of(value),expectedConnectionRevision,batchSize);}
    public IndexCreateInput clearExpectedActiveId(){return new IndexCreateInput(workspaceId,domain,providerId,modelId,expectedDimensions,JsonField.clear(),expectedConnectionRevision,batchSize);}
    public IndexCreateInput omitExpectedActiveId(){return new IndexCreateInput(workspaceId,domain,providerId,modelId,expectedDimensions,null,expectedConnectionRevision,batchSize);}
    public IndexCreateInput withExpectedConnectionRevision(Long value){return new IndexCreateInput(workspaceId,domain,providerId,modelId,expectedDimensions,expectedActiveId,JsonField.of(value),batchSize);}
    public IndexCreateInput clearExpectedConnectionRevision(){return new IndexCreateInput(workspaceId,domain,providerId,modelId,expectedDimensions,expectedActiveId,JsonField.clear(),batchSize);}
    public IndexCreateInput omitExpectedConnectionRevision(){return new IndexCreateInput(workspaceId,domain,providerId,modelId,expectedDimensions,expectedActiveId,null,batchSize);}
    public IndexCreateInput withBatchSize(Integer value){return new IndexCreateInput(workspaceId,domain,providerId,modelId,expectedDimensions,expectedActiveId,expectedConnectionRevision,value);}
}
