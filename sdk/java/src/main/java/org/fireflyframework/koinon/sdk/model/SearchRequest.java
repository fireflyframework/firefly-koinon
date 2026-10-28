// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SearchRequest contract. */
public record SearchRequest(
    @JsonProperty("question") String question,
    @JsonProperty("workspace_id") JsonField<String> workspaceId,
    @JsonProperty("project_id") JsonField<String> projectId,
    @JsonProperty("collection_id") JsonField<String> collectionId,
    @JsonProperty("asset_ids") JsonField<List<String>> assetIds,
    @JsonProperty("limit") Long limit,
    @JsonProperty("answer") Boolean answer
) {

    public static SearchRequest empty(){return new SearchRequest(null,null,null,null,null,null,null);}
    public SearchRequest withQuestion(String value){return new SearchRequest(value,workspaceId,projectId,collectionId,assetIds,limit,answer);}
    public SearchRequest withWorkspaceId(String value){return new SearchRequest(question,JsonField.of(value),projectId,collectionId,assetIds,limit,answer);}
    public SearchRequest clearWorkspaceId(){return new SearchRequest(question,JsonField.clear(),projectId,collectionId,assetIds,limit,answer);}
    public SearchRequest omitWorkspaceId(){return new SearchRequest(question,null,projectId,collectionId,assetIds,limit,answer);}
    public SearchRequest withProjectId(String value){return new SearchRequest(question,workspaceId,JsonField.of(value),collectionId,assetIds,limit,answer);}
    public SearchRequest clearProjectId(){return new SearchRequest(question,workspaceId,JsonField.clear(),collectionId,assetIds,limit,answer);}
    public SearchRequest omitProjectId(){return new SearchRequest(question,workspaceId,null,collectionId,assetIds,limit,answer);}
    public SearchRequest withCollectionId(String value){return new SearchRequest(question,workspaceId,projectId,JsonField.of(value),assetIds,limit,answer);}
    public SearchRequest clearCollectionId(){return new SearchRequest(question,workspaceId,projectId,JsonField.clear(),assetIds,limit,answer);}
    public SearchRequest omitCollectionId(){return new SearchRequest(question,workspaceId,projectId,null,assetIds,limit,answer);}
    public SearchRequest withAssetIds(List<String> value){return new SearchRequest(question,workspaceId,projectId,collectionId,JsonField.of(value),limit,answer);}
    public SearchRequest clearAssetIds(){return new SearchRequest(question,workspaceId,projectId,collectionId,JsonField.clear(),limit,answer);}
    public SearchRequest omitAssetIds(){return new SearchRequest(question,workspaceId,projectId,collectionId,null,limit,answer);}
    public SearchRequest withLimit(Long value){return new SearchRequest(question,workspaceId,projectId,collectionId,assetIds,value,answer);}
    public SearchRequest withAnswer(Boolean value){return new SearchRequest(question,workspaceId,projectId,collectionId,assetIds,limit,value);}
}
