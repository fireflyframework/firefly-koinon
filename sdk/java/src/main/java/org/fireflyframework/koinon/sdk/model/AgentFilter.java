// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record AgentFilter(String q,Integer page,Integer pageSize,String status,String workspaceId,String projectId,String sort,String order) {
public static AgentFilter empty(){return new AgentFilter(null,null,null,null,null,null,null,null);}
public AgentFilter withQ(String value){return new AgentFilter(value,page,pageSize,status,workspaceId,projectId,sort,order);}
public AgentFilter withPage(Integer value){return new AgentFilter(q,value,pageSize,status,workspaceId,projectId,sort,order);}
public AgentFilter withPageSize(Integer value){return new AgentFilter(q,page,value,status,workspaceId,projectId,sort,order);}
public AgentFilter withStatus(String value){return new AgentFilter(q,page,pageSize,value,workspaceId,projectId,sort,order);}
public AgentFilter withWorkspaceId(String value){return new AgentFilter(q,page,pageSize,status,value,projectId,sort,order);}
public AgentFilter withProjectId(String value){return new AgentFilter(q,page,pageSize,status,workspaceId,value,sort,order);}
public AgentFilter withSort(String value){return new AgentFilter(q,page,pageSize,status,workspaceId,projectId,value,order);}
public AgentFilter withOrder(String value){return new AgentFilter(q,page,pageSize,status,workspaceId,projectId,sort,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
if(status!=null)options=options.query("status",String.valueOf(status));
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(projectId!=null)options=options.query("project_id",String.valueOf(projectId));
if(sort!=null)options=options.query("sort",String.valueOf(sort));
if(order!=null)options=options.query("order",String.valueOf(order));
return options;}
}
