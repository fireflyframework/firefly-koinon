// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record ThreadFilter(String q,Integer page,Integer pageSize,String sort,String order,String folderId,Boolean unfiled,String projectId,String workspaceId,String status) {
public static ThreadFilter empty(){return new ThreadFilter(null,null,null,null,null,null,null,null,null,null);}
public ThreadFilter withQ(String value){return new ThreadFilter(value,page,pageSize,sort,order,folderId,unfiled,projectId,workspaceId,status);}
public ThreadFilter withPage(Integer value){return new ThreadFilter(q,value,pageSize,sort,order,folderId,unfiled,projectId,workspaceId,status);}
public ThreadFilter withPageSize(Integer value){return new ThreadFilter(q,page,value,sort,order,folderId,unfiled,projectId,workspaceId,status);}
public ThreadFilter withSort(String value){return new ThreadFilter(q,page,pageSize,value,order,folderId,unfiled,projectId,workspaceId,status);}
public ThreadFilter withOrder(String value){return new ThreadFilter(q,page,pageSize,sort,value,folderId,unfiled,projectId,workspaceId,status);}
public ThreadFilter withFolderId(String value){return new ThreadFilter(q,page,pageSize,sort,order,value,unfiled,projectId,workspaceId,status);}
public ThreadFilter withUnfiled(Boolean value){return new ThreadFilter(q,page,pageSize,sort,order,folderId,value,projectId,workspaceId,status);}
public ThreadFilter withProjectId(String value){return new ThreadFilter(q,page,pageSize,sort,order,folderId,unfiled,value,workspaceId,status);}
public ThreadFilter withWorkspaceId(String value){return new ThreadFilter(q,page,pageSize,sort,order,folderId,unfiled,projectId,value,status);}
public ThreadFilter withStatus(String value){return new ThreadFilter(q,page,pageSize,sort,order,folderId,unfiled,projectId,workspaceId,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
if(sort!=null)options=options.query("sort",String.valueOf(sort));
if(order!=null)options=options.query("order",String.valueOf(order));
if(folderId!=null)options=options.query("folder_id",String.valueOf(folderId));
if(unfiled!=null)options=options.query("unfiled",String.valueOf(unfiled));
if(projectId!=null)options=options.query("project_id",String.valueOf(projectId));
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(status!=null)options=options.query("status",String.valueOf(status));
return options;}
}
