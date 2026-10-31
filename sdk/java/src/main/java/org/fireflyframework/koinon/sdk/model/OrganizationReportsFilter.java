// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record OrganizationReportsFilter(String workspaceId,Integer page,Integer pageSize) {
public static OrganizationReportsFilter empty(){return new OrganizationReportsFilter(null,null,null);}
public OrganizationReportsFilter withWorkspaceId(String value){return new OrganizationReportsFilter(value,page,pageSize);}
public OrganizationReportsFilter withPage(Integer value){return new OrganizationReportsFilter(workspaceId,value,pageSize);}
public OrganizationReportsFilter withPageSize(Integer value){return new OrganizationReportsFilter(workspaceId,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}
