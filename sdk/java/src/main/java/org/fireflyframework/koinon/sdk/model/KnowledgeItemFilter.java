// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record KnowledgeItemFilter(String workspaceId,String projectId,String destinationId,String q,Integer page,Integer pageSize) {
public static KnowledgeItemFilter empty(){return new KnowledgeItemFilter(null,null,null,null,null,null);}
public KnowledgeItemFilter withWorkspaceId(String value){return new KnowledgeItemFilter(value,projectId,destinationId,q,page,pageSize);}
public KnowledgeItemFilter withProjectId(String value){return new KnowledgeItemFilter(workspaceId,value,destinationId,q,page,pageSize);}
public KnowledgeItemFilter withDestinationId(String value){return new KnowledgeItemFilter(workspaceId,projectId,value,q,page,pageSize);}
public KnowledgeItemFilter withQ(String value){return new KnowledgeItemFilter(workspaceId,projectId,destinationId,value,page,pageSize);}
public KnowledgeItemFilter withPage(Integer value){return new KnowledgeItemFilter(workspaceId,projectId,destinationId,q,value,pageSize);}
public KnowledgeItemFilter withPageSize(Integer value){return new KnowledgeItemFilter(workspaceId,projectId,destinationId,q,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(projectId!=null)options=options.query("project_id",String.valueOf(projectId));
if(destinationId!=null)options=options.query("destination_id",String.valueOf(destinationId));
if(q!=null)options=options.query("q",String.valueOf(q));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}
