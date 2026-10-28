// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AddKnowledge contract. */
public record AddKnowledge(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("action") AddKnowledgeAction action,
    @JsonProperty("mode") AddKnowledgeMode mode,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("project_id") String projectId,
    @JsonProperty("parent_id") String parentId
) implements AttachmentPromotionInput {

    public static AddKnowledge empty(){return new AddKnowledge(null,null,null,null,null,null);}
    public AddKnowledge withExpectedRevision(Long value){return new AddKnowledge(value,action,mode,workspaceId,projectId,parentId);}
    public AddKnowledge withAction(AddKnowledgeAction value){return new AddKnowledge(expectedRevision,value,mode,workspaceId,projectId,parentId);}
    public AddKnowledge withMode(AddKnowledgeMode value){return new AddKnowledge(expectedRevision,action,value,workspaceId,projectId,parentId);}
    public AddKnowledge withWorkspaceId(String value){return new AddKnowledge(expectedRevision,action,mode,value,projectId,parentId);}
    public AddKnowledge withProjectId(String value){return new AddKnowledge(expectedRevision,action,mode,workspaceId,value,parentId);}
    public AddKnowledge withParentId(String value){return new AddKnowledge(expectedRevision,action,mode,workspaceId,projectId,value);}
}
