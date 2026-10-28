// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record CatalogFilter(String kind,String parentId,String workspaceId,String projectId,Boolean includeArchived,String view,String q,String status,String format,String tag,Integer page,Integer pageSize,String sort,String order) {
public static CatalogFilter empty(){return new CatalogFilter(null,null,null,null,null,null,null,null,null,null,null,null,null,null);}
public CatalogFilter(String kind,String parentId,String workspaceId,String projectId,Boolean includeArchived,String view,String q,String status,Integer page,Integer pageSize,String sort,String order){this(kind,parentId,workspaceId,projectId,includeArchived,view,q,status,null,null,page,pageSize,sort,order);}
public CatalogFilter withKind(String value){return new CatalogFilter(value,parentId,workspaceId,projectId,includeArchived,view,q,status,format,tag,page,pageSize,sort,order);}
public CatalogFilter withParentId(String value){return new CatalogFilter(kind,value,workspaceId,projectId,includeArchived,view,q,status,format,tag,page,pageSize,sort,order);}
public CatalogFilter withWorkspaceId(String value){return new CatalogFilter(kind,parentId,value,projectId,includeArchived,view,q,status,format,tag,page,pageSize,sort,order);}
public CatalogFilter withProjectId(String value){return new CatalogFilter(kind,parentId,workspaceId,value,includeArchived,view,q,status,format,tag,page,pageSize,sort,order);}
public CatalogFilter withIncludeArchived(Boolean value){return new CatalogFilter(kind,parentId,workspaceId,projectId,value,view,q,status,format,tag,page,pageSize,sort,order);}
public CatalogFilter withView(String value){return new CatalogFilter(kind,parentId,workspaceId,projectId,includeArchived,value,q,status,format,tag,page,pageSize,sort,order);}
public CatalogFilter withQ(String value){return new CatalogFilter(kind,parentId,workspaceId,projectId,includeArchived,view,value,status,format,tag,page,pageSize,sort,order);}
public CatalogFilter withStatus(String value){return new CatalogFilter(kind,parentId,workspaceId,projectId,includeArchived,view,q,value,format,tag,page,pageSize,sort,order);}
public CatalogFilter withFormat(String value){return new CatalogFilter(kind,parentId,workspaceId,projectId,includeArchived,view,q,status,value,tag,page,pageSize,sort,order);}
public CatalogFilter withTag(String value){return new CatalogFilter(kind,parentId,workspaceId,projectId,includeArchived,view,q,status,format,value,page,pageSize,sort,order);}
public CatalogFilter withPage(Integer value){return new CatalogFilter(kind,parentId,workspaceId,projectId,includeArchived,view,q,status,format,tag,value,pageSize,sort,order);}
public CatalogFilter withPageSize(Integer value){return new CatalogFilter(kind,parentId,workspaceId,projectId,includeArchived,view,q,status,format,tag,page,value,sort,order);}
public CatalogFilter withSort(String value){return new CatalogFilter(kind,parentId,workspaceId,projectId,includeArchived,view,q,status,format,tag,page,pageSize,value,order);}
public CatalogFilter withOrder(String value){return new CatalogFilter(kind,parentId,workspaceId,projectId,includeArchived,view,q,status,format,tag,page,pageSize,sort,value);}
public RequestOptions applyTo(RequestOptions options){
if(kind!=null)options=options.query("kind",String.valueOf(kind));
if(parentId!=null)options=options.query("parent_id",String.valueOf(parentId));
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(projectId!=null)options=options.query("project_id",String.valueOf(projectId));
if(includeArchived!=null)options=options.query("include_archived",String.valueOf(includeArchived));
if(view!=null)options=options.query("view",String.valueOf(view));
if(q!=null)options=options.query("q",String.valueOf(q));
if(status!=null)options=options.query("status",String.valueOf(status));
if(format!=null)options=options.query("format",String.valueOf(format));
if(tag!=null)options=options.query("tag",String.valueOf(tag));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
if(sort!=null)options=options.query("sort",String.valueOf(sort));
if(order!=null)options=options.query("order",String.valueOf(order));
return options;}
}
