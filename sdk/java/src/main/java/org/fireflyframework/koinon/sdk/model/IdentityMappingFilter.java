// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record IdentityMappingFilter(String q,String status,String workspaceId,Integer page,Integer pageSize) {
public static IdentityMappingFilter empty(){return new IdentityMappingFilter(null,null,null,null,null);}
public IdentityMappingFilter withQ(String value){return new IdentityMappingFilter(value,status,workspaceId,page,pageSize);}
public IdentityMappingFilter withStatus(String value){return new IdentityMappingFilter(q,value,workspaceId,page,pageSize);}
public IdentityMappingFilter withWorkspaceId(String value){return new IdentityMappingFilter(q,status,value,page,pageSize);}
public IdentityMappingFilter withPage(Integer value){return new IdentityMappingFilter(q,status,workspaceId,value,pageSize);}
public IdentityMappingFilter withPageSize(Integer value){return new IdentityMappingFilter(q,status,workspaceId,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(status!=null)options=options.query("status",String.valueOf(status));
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}
