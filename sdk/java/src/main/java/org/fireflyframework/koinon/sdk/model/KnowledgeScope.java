// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical KnowledgeScope contract. */
public record KnowledgeScope(
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("project_id") String projectId,
    @JsonProperty("collection_id") String collectionId,
    @JsonProperty("asset_ids") List<String> assetIds
) {
    public KnowledgeScope {
        assetIds=assetIds==null?null:List.copyOf(assetIds);
    }

    public static KnowledgeScope empty(){return new KnowledgeScope(null,null,null,null);}
    public KnowledgeScope withWorkspaceId(String value){return new KnowledgeScope(value,projectId,collectionId,assetIds);}
    public KnowledgeScope withProjectId(String value){return new KnowledgeScope(workspaceId,value,collectionId,assetIds);}
    public KnowledgeScope withCollectionId(String value){return new KnowledgeScope(workspaceId,projectId,value,assetIds);}
    public KnowledgeScope withAssetIds(List<String> value){return new KnowledgeScope(workspaceId,projectId,collectionId,value);}
}
