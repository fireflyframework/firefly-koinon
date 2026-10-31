// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical QueryBatchCreate contract. */
public record QueryBatchCreate(
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("processing_policy") QueryBatchCapabilitiesProcessingPolicy processingPolicy,
    @JsonProperty("items") List<QueryManifestItem> items
) {
    public QueryBatchCreate {
        items=items==null?null:List.copyOf(items);
    }

    public static QueryBatchCreate empty(){return new QueryBatchCreate(null,null,null);}
    public QueryBatchCreate withWorkspaceId(String value){return new QueryBatchCreate(value,processingPolicy,items);}
    public QueryBatchCreate withProcessingPolicy(QueryBatchCapabilitiesProcessingPolicy value){return new QueryBatchCreate(workspaceId,value,items);}
    public QueryBatchCreate withItems(List<QueryManifestItem> value){return new QueryBatchCreate(workspaceId,processingPolicy,value);}
}
