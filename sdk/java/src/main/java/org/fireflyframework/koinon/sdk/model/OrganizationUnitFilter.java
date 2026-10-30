// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record OrganizationUnitFilter(String workspaceId,String parentId,String q,Integer page,Integer pageSize) {
public static OrganizationUnitFilter empty(){return new OrganizationUnitFilter(null,null,null,null,null);}
public OrganizationUnitFilter withWorkspaceId(String value){return new OrganizationUnitFilter(value,parentId,q,page,pageSize);}
public OrganizationUnitFilter withParentId(String value){return new OrganizationUnitFilter(workspaceId,value,q,page,pageSize);}
public OrganizationUnitFilter withQ(String value){return new OrganizationUnitFilter(workspaceId,parentId,value,page,pageSize);}
public OrganizationUnitFilter withPage(Integer value){return new OrganizationUnitFilter(workspaceId,parentId,q,value,pageSize);}
public OrganizationUnitFilter withPageSize(Integer value){return new OrganizationUnitFilter(workspaceId,parentId,q,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(parentId!=null)options=options.query("parent_id",String.valueOf(parentId));
if(q!=null)options=options.query("q",String.valueOf(q));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}
