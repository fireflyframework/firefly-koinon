// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record FolderFilter(String q,Integer page,Integer pageSize,String parentId,Boolean rootOnly,String workspaceId,String sort,String order) {
public static FolderFilter empty(){return new FolderFilter(null,null,null,null,null,null,null,null);}
public FolderFilter withQ(String value){return new FolderFilter(value,page,pageSize,parentId,rootOnly,workspaceId,sort,order);}
public FolderFilter withPage(Integer value){return new FolderFilter(q,value,pageSize,parentId,rootOnly,workspaceId,sort,order);}
public FolderFilter withPageSize(Integer value){return new FolderFilter(q,page,value,parentId,rootOnly,workspaceId,sort,order);}
public FolderFilter withParentId(String value){return new FolderFilter(q,page,pageSize,value,rootOnly,workspaceId,sort,order);}
public FolderFilter withRootOnly(Boolean value){return new FolderFilter(q,page,pageSize,parentId,value,workspaceId,sort,order);}
public FolderFilter withWorkspaceId(String value){return new FolderFilter(q,page,pageSize,parentId,rootOnly,value,sort,order);}
public FolderFilter withSort(String value){return new FolderFilter(q,page,pageSize,parentId,rootOnly,workspaceId,value,order);}
public FolderFilter withOrder(String value){return new FolderFilter(q,page,pageSize,parentId,rootOnly,workspaceId,sort,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
if(parentId!=null)options=options.query("parent_id",String.valueOf(parentId));
if(rootOnly!=null)options=options.query("root_only",String.valueOf(rootOnly));
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(sort!=null)options=options.query("sort",String.valueOf(sort));
if(order!=null)options=options.query("order",String.valueOf(order));
return options;}
}
