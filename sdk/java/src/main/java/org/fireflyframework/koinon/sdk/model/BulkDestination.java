// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical BulkDestination contract. */
public record BulkDestination(
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("project_id") String projectId,
    @JsonProperty("parent_id") String parentId
) {

    public static BulkDestination empty(){return new BulkDestination(null,null,null);}
    public BulkDestination withWorkspaceId(String value){return new BulkDestination(value,projectId,parentId);}
    public BulkDestination withProjectId(String value){return new BulkDestination(workspaceId,value,parentId);}
    public BulkDestination withParentId(String value){return new BulkDestination(workspaceId,projectId,value);}
}
